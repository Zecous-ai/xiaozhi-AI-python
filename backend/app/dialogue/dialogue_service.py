from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.communication.session import ChatSession
from app.dialogue.llm_service import OpenAIClient
from app.dialogue.message_service import MessageService
from app.services.config_service import SysConfigService
from app.services.role_service import SysRoleService
from app.services.sys_message_service import SysMessageService

logger = logging.getLogger("dialogue_service")


class DialogueService:
    def __init__(
        self,
        config_service: SysConfigService,
        role_service: SysRoleService,
        message_service: MessageService,
        sys_message_service: SysMessageService,
    ) -> None:
        self.config_service = config_service
        self.role_service = role_service
        self.message_service = message_service
        self.sys_message_service = sys_message_service

    async def handle_text(self, session: ChatSession, text: str) -> None:
        if not text:
            return
        device = session.sys_device or {}
        role_id = device.get("roleId")
        if not role_id:
            await self.message_service.send_tts_message(session, "设备未绑定角色", "stop")
            return
        role = self.role_service.select_role_by_id(int(role_id))
        if not role:
            await self.message_service.send_tts_message(session, "角色不存在", "stop")
            return

        model_id = role.get("modelId")
        if not model_id:
            await self.message_service.send_tts_message(session, "未配置模型", "stop")
            return
        config = self.config_service.select_config_by_id(int(model_id))
        if not config:
            await self.message_service.send_tts_message(session, "模型配置不存在", "stop")
            return

        system_prompt = role.get("roleDesc") or "你是一个乐于助人的AI助手。"
        provider = (config.get("provider") or "").lower()
        api_url = config.get("apiUrl") or "https://api.openai.com/v1"
        api_key = config.get("apiKey") or ""
        model = config.get("configName") or config.get("modelType") or "gpt-3.5-turbo"

        if provider in ("openai", "openai-compatible", "zhipuai", "ollama", "openrouter", "volcengine"):
            client = OpenAIClient(api_url, api_key, model)
            reply = client.chat(system_prompt, text)
        else:
            # 默认使用 OpenAI 兼容协议
            client = OpenAIClient(api_url, api_key, model)
            reply = client.chat(system_prompt, text)

        if reply is None:
            await self.message_service.send_tts_message(session, "对话失败，请检查模型配置", "stop")
            return

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        # 保存用户和助手消息
        self.sys_message_service.add(
            {
                "deviceId": device.get("deviceId"),
                "sessionId": session.session_id,
                "sender": "user",
                "roleId": role_id,
                "message": text,
                "messageType": "NORMAL",
                "createTime": now,
            }
        )
        self.sys_message_service.add(
            {
                "deviceId": device.get("deviceId"),
                "sessionId": session.session_id,
                "sender": "assistant",
                "roleId": role_id,
                "message": reply,
                "messageType": "NORMAL",
                "createTime": now,
            }
        )

        await self.message_service.send_stt_message(session, text)
        await self.message_service.send_tts_message(session, reply, "stop")

    async def handle_audio(self, session: ChatSession, audio: bytes) -> None:
        if not audio:
            return
        # 暂不支持音频识别，直接提示
        await self.message_service.send_tts_message(session, "暂不支持音频识别，请使用文本输入。", "stop")

    async def handle_wake_word(self, session: ChatSession, text: str) -> None:
        await self.message_service.send_tts_message(session, "你好，我在。", "stop")

    async def abort(self, session: ChatSession, reason: Optional[str]) -> None:
        _ = reason
        await self.message_service.send_tts_message(session, "已中止", "stop")


__all__ = ["DialogueService"]
