from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict

from app.communication.messages import (
    AbortMessage,
    DeviceMcpMessage,
    GoodbyeMessage,
    HelloMessage,
    HelloMessageResp,
    ListenMessage,
    IotMessage,
    AudioParams,
    parse_message,
)
from app.communication.session import ChatSession, session_manager
from app.dialogue.device_mcp import DeviceMcpService
from app.dialogue.iot_service import IotService
from app.dialogue.sentence import Sentence
from app.dialogue.file_player import FilePlayer
from app.dialogue.tts.factory import TtsServiceFactory
from app.dialogue.stt.factory import SttServiceFactory
from app.dialogue.message_service import MessageService
from app.dialogue.vad.vad_service import VadService
from app.dialogue.memory import ConversationFactory
from app.dialogue.tools import ToolsGlobalRegistry, ToolsSessionHolder
from app.services.device_service import SysDeviceService
from app.services.config_service import SysConfigService
from app.services.role_service import SysRoleService
from app.services.sys_message_service import SysMessageService

logger = logging.getLogger("message_handler")


class MessageHandler:
    def __init__(
        self,
        device_service: SysDeviceService,
        config_service: SysConfigService,
        role_service: SysRoleService,
        message_service: MessageService,
        sys_message_service: SysMessageService,
        vad_service: VadService,
        dialogue_service,
        tts_factory: TtsServiceFactory,
        stt_factory: SttServiceFactory,
        conversation_factory: ConversationFactory,
        tools_registry: ToolsGlobalRegistry,
        iot_service: IotService,
        device_mcp_service: DeviceMcpService,
    ) -> None:
        self.device_service = device_service
        self.config_service = config_service
        self.role_service = role_service
        self.message_service = message_service
        self.sys_message_service = sys_message_service
        self.vad_service = vad_service
        self.dialogue_service = dialogue_service
        self.tts_factory = tts_factory
        self.stt_factory = stt_factory
        self.conversation_factory = conversation_factory
        self.tools_registry = tools_registry
        self.iot_service = iot_service
        self.device_mcp_service = device_mcp_service

    async def after_connection(self, chat_session: ChatSession, device_id: str) -> None:
        session_manager.register_session(chat_session.session_id, chat_session)
        logger.info("开始查询设备信息- DeviceId: %s", device_id)
        device = self.device_service.select_device_by_id(device_id)
        if device is None:
            device = {"deviceId": device_id}
        device["deviceId"] = device_id
        device["sessionId"] = chat_session.session_id
        session_manager.register_device(chat_session.session_id, device)
        if device.get("roleId"):
            self._initialize_bound_device(chat_session, device)

    async def after_connection_closed(self, session_id: str) -> None:
        session = session_manager.get_session(session_id)
        if not session:
            return
        if session.sys_device:
            device_id = session.sys_device.get("deviceId")
            if device_id:
                def _update_state():
                    try:
                        current_session = session_manager.get_session_by_device_id(device_id)
                        if current_session is not None and current_session.session_id != session_id:
                            return
                        new_state = "0" if session.websocket is not None else "2"
                        self.device_service.update({"deviceId": device_id, "state": new_state, "lastLogin": True})
                        logger.info(
                            "连接已关闭- SessionId: %s, DeviceId: %s, 新状态: %s",
                            session_id,
                            device_id,
                            new_state,
                        )
                    except Exception as exc:
                        logger.error("更新设备状态失败: %s", exc)

                threading.Thread(target=_update_state, daemon=True).start()
        session_manager.close_session(session_id)
        self.vad_service.reset_session(session_id)
        if session:
            self.dialogue_service.cleanup_session(session)

    def _initialize_bound_device(self, chat_session: ChatSession, device: dict) -> None:
        session_id = chat_session.session_id
        tools_holder = ToolsSessionHolder(session_id, device, self.tools_registry)
        chat_session.tools_session_holder = tools_holder

        role_id = device.get("roleId")
        role = self.role_service.select_role_by_id(int(role_id)) if role_id else None
        if role:
            chat_session.conversation = self.conversation_factory.init_conversation(device, role, session_id)

        def _bootstrap():
            try:
                if role and role.get("sttId"):
                    stt_config = self.config_service.select_config_by_id(int(role.get("sttId")))
                    if stt_config:
                        self.stt_factory.get_stt_service(stt_config)
                if role and role.get("ttsId"):
                    tts_config = self.config_service.select_config_by_id(int(role.get("ttsId")))
                    if tts_config:
                        self.tts_factory.get_tts_service(
                            tts_config,
                            role.get("voiceName"),
                            float(role.get("ttsPitch") or 1.0),
                            float(role.get("ttsSpeed") or 1.0),
                        )
                state = "1" if chat_session.websocket is not None else "2"
                self.device_service.update({"deviceId": device.get("deviceId"), "state": state, "lastLogin": True})
            except Exception as exc:
                logger.error("设备初始化失败: %s", exc)
                try:
                    session_manager.close_session(session_id)
                except Exception:
                    logger.exception("关闭连接失败")

        threading.Thread(target=_bootstrap, daemon=True).start()

    async def handle_text_message(self, session_id: str, payload: str) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            logger.exception("解析消息失败")
            return
        msg = parse_message(data)
        session = session_manager.get_session(session_id)
        if session is None:
            return
        if isinstance(msg, HelloMessage):
            await self._handle_hello(session, msg)
            return
        device = session.sys_device or {}
        if not device.get("roleId"):
            auto_bound = self.handle_unbound_device(session_id, device)
            if not auto_bound:
                return
        if isinstance(msg, ListenMessage):
            await self._handle_listen(session, msg)
            return
        if isinstance(msg, IotMessage):
            if msg.descriptors:
                logger.info("收到IoT设备描述信息 - SessionId: %s: %s", session_id, msg.descriptors)
                self.iot_service.handle_device_descriptors(session_id, msg.descriptors)
            if msg.states:
                logger.info("收到IoT设备状态更新- SessionId: %s: %s", session_id, msg.states)
                self.iot_service.handle_device_states(session_id, msg.states)
            return
        if isinstance(msg, AbortMessage):
            self.dialogue_service.abort_dialogue(session, msg.reason)
            return
        if isinstance(msg, GoodbyeMessage):
            self.vad_service.reset_session(session_id)
            self.dialogue_service.abort_dialogue(session, "设备主动退出")
            session_manager.close_session(session_id)
            if session.websocket is None and session.sys_device:
                device_id = session.sys_device.get("deviceId")
                if device_id:
                    def _mark_standby():
                        try:
                            self.device_service.update({"deviceId": device_id, "state": "2", "lastLogin": True})
                            logger.info("设备连接进入待机状态- SessionId: %s, DeviceId: %s", session_id, device_id)
                        except Exception as exc:
                            logger.error("更新设备状态失败: %s", exc)

                    threading.Thread(target=_mark_standby, daemon=True).start()
            return
        if isinstance(msg, DeviceMcpMessage):
            self.device_mcp_service.handle_mcp_response(session, msg.model_dump())
            return

    async def handle_binary_message(self, session_id: str, data: bytes) -> None:
        session = session_manager.get_session(session_id)
        if (session is None or not session.is_open()) and not self.vad_service.is_session_initialized(session_id):
            return
        self.dialogue_service.process_audio_data(session, data)

    async def _handle_hello(self, session: ChatSession, message: HelloMessage) -> None:
        resp = HelloMessageResp(
            transport="websocket",
            session_id=session.session_id,
            audio_params=AudioParams.opus(),
        )
        await session.send_text_message(resp.model_dump_json(by_alias=True))
        if message.features and message.features.mcp:
            threading.Thread(target=self._init_mcp_async, args=(session,), daemon=True).start()

    def _init_mcp_async(self, session: ChatSession) -> None:
        try:
            if session.sys_device and session.sys_device.get("roleId"):
                asyncio.run(self.device_mcp_service.initialize(session))
        except Exception:
            logger.exception("MCP 初始化失败")

    async def _handle_listen(self, session: ChatSession, message: ListenMessage) -> None:
        state = (message.state or "").lower()
        session.mode = message.mode
        logger.info(
            "收到listen消息 - SessionId: %s, State: %s, Mode: %s",
            session.session_id,
            message.state,
            message.mode,
        )
        if session.close_after_chat:
            return
        if state == "start":
            logger.info("开始监听- Mode: %s", message.mode)
            if session.in_wakeup_response:
                await self.message_service.send_tts_message(session, None, "start")
            self.vad_service.init_session(session.session_id)
            return
        if state == "stop":
            logger.info("停止监听")
            session_manager.complete_audio_stream(session.session_id)
            session_manager.close_audio_stream(session.session_id)
            session_manager.set_streaming_state(session.session_id, False)
            self.vad_service.reset_session(session.session_id)
            return
        if state == "text":
            if session.player:
                self.dialogue_service.abort_dialogue(session, message.mode or "")
            await self.dialogue_service.handle_text(session, message.text or "")
            return
        if state == "detect":
            await self.dialogue_service.handle_wake_word(session, message.text or "")
            return
        logger.warning("未知的listen状态: %s", message.state)

    def handle_unbound_device(self, session_id: str, device: Dict[str, Any]) -> bool:
        if not device or not device.get("deviceId"):
            return False
        device_id = device.get("deviceId")

        if device_id.startswith("user_chat_"):
            try:
                logger.info("检测到虚拟设备 %s，尝试自动绑定", device_id)
                user_id = int(device_id.replace("user_chat_", ""))
                roles = self.role_service.query({"userId": user_id})
                if roles:
                    default_role = next((r for r in roles if str(r.get("isDefault")) == "1"), roles[0])
                    virtual_device = {
                        "deviceId": device_id,
                        "deviceName": "小助手",
                        "userId": user_id,
                        "type": "web",
                        "state": "1",
                        "roleId": default_role.get("roleId"),
                    }
                    self.device_service.add(virtual_device)
                    bound = self.device_service.select_device_by_id(device_id)
                    if bound:
                        bound["sessionId"] = session_id
                        session_manager.register_device(session_id, bound)
                        session = session_manager.get_session(session_id)
                        if session:
                            self._initialize_bound_device(session, bound)
                        logger.info("虚拟设备 %s 自动绑定成功，角色ID: %s", device_id, default_role.get("roleId"))
                        return True
                logger.warning("用户 %s 没有可用角色，无法自动绑定虚拟设备", user_id)
            except ValueError:
                logger.error("解析虚拟设备ID失败: %s", device_id)
            except Exception as exc:
                logger.error("自动绑定虚拟设备失败: %s", exc)

        session = session_manager.get_session(session_id)
        if session is None or not session.is_open():
            return False
        if not session_manager.mark_captcha_generation(device_id):
            return False

        def _task():
            try:
                player = FilePlayer(session, self.message_service, session_manager, self.sys_message_service)
                if device.get("deviceName") and not device.get("roleId"):
                    message = "设备未配置角色，请到角色配置页面完成配置后开始对话"
                    audio_path = self.tts_factory.get_default_tts_service().text_to_speech(message)
                    player.append(Sentence(message, audio_path))
                    player.play()
                    time.sleep(1)
                    return

                code_result = self.device_service.generate_code(device_id, session_id, device.get("type"))
                audio_path = code_result.get("audioPath")
                if not audio_path:
                    code_message = f"请到设备管理页面添加设备，输入验证码{code_result.get('code')}"
                    audio_path = self.tts_factory.get_default_tts_service().text_to_speech(code_message)
                    self.device_service.update_code(device_id, session_id, code_result.get("code"), audio_path)
                player.append(Sentence(code_result.get("code"), audio_path))
                player.play()
                time.sleep(1)
            except Exception:
                logger.exception("处理未绑定设备失败")
            finally:
                session_manager.unmark_captcha_generation(device_id)

        threading.Thread(target=_task, daemon=True).start()
        return False


__all__ = ["MessageHandler"]
