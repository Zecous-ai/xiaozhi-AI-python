from __future__ import annotations

import json
import logging
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
from app.services.device_service import SysDeviceService
from app.dialogue.dialogue_service import DialogueService

logger = logging.getLogger("message_handler")


class MessageHandler:
    def __init__(self, device_service: SysDeviceService, dialogue_service: DialogueService) -> None:
        self.device_service = device_service
        self.dialogue_service = dialogue_service

    async def after_connection(self, chat_session: ChatSession, device_id: str) -> None:
        session_manager.register_session(chat_session.session_id, chat_session)
        device = self.device_service.select_device_by_id(device_id)
        if device is None:
            device = {"deviceId": device_id}
        device["deviceId"] = device_id
        device["sessionId"] = chat_session.session_id
        session_manager.register_device(chat_session.session_id, device)

    async def after_connection_closed(self, session_id: str) -> None:
        session_manager.remove_session(session_id)

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
        if isinstance(msg, ListenMessage):
            await self._handle_listen(session, msg)
            return
        if isinstance(msg, IotMessage):
            # IoT 消息目前仅记录
            logger.info("收到 IoT 消息 session=%s", session_id)
            return
        if isinstance(msg, AbortMessage):
            await self.dialogue_service.abort(session, msg.reason)
            return
        if isinstance(msg, GoodbyeMessage):
            await session.close()
            session_manager.remove_session(session_id)
            return
        if isinstance(msg, DeviceMcpMessage):
            # 设备 MCP 暂不实现
            return

    async def handle_binary_message(self, session_id: str, data: bytes) -> None:
        session_manager.append_audio(session_id, data)

    async def _handle_hello(self, session: ChatSession, message: HelloMessage) -> None:
        resp = HelloMessageResp(
            transport="websocket",
            session_id=session.session_id,
            audio_params=AudioParams.opus(),
        )
        await session.send_text_message(resp.model_dump_json(by_alias=True))

    async def _handle_listen(self, session: ChatSession, message: ListenMessage) -> None:
        state = (message.state or "").lower()
        session.mode = message.mode
        if state == "start":
            session.audio_buffer.clear()
            session_manager.set_streaming_state(session.session_id, True)
            return
        if state == "stop":
            session_manager.set_streaming_state(session.session_id, False)
            audio = session_manager.pop_audio(session.session_id)
            await self.dialogue_service.handle_audio(session, audio)
            return
        if state == "text":
            await self.dialogue_service.handle_text(session, message.text or "")
            return
        if state == "detect":
            await self.dialogue_service.handle_wake_word(session, message.text or "")
            return


__all__ = ["MessageHandler"]
