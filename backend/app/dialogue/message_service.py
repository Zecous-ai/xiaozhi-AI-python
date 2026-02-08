from __future__ import annotations

import json
import logging
from typing import List, Dict, Optional

from app.communication.session import ChatSession
from app.utils.async_utils import schedule_coro

logger = logging.getLogger("dialogue_message_service")


class MessageService:
    async def send_tts_message(self, session: ChatSession, text: Optional[str], state: str) -> None:
        if not session or not session.is_open():
            return
        payload = {"type": "tts", "state": state}
        if text is not None:
            payload["text"] = text
        await session.send_text_message(json.dumps(payload, ensure_ascii=False))

    async def send_stt_message(self, session: ChatSession, text: str) -> None:
        if not session or not session.is_open():
            return
        payload = {"type": "stt", "text": text}
        await session.send_text_message(json.dumps(payload, ensure_ascii=False))

    def send_iot_command(self, session: ChatSession, commands: List[Dict]) -> bool:
        if not session or not session.is_open():
            return False
        payload = {"session_id": session.session_id, "type": "iot", "commands": commands}
        schedule_coro(session.send_text_message(json.dumps(payload, ensure_ascii=False)))
        return True

    async def send_emotion(self, session: ChatSession, emotion: str) -> None:
        if not session or not session.is_open():
            return
        payload = {"session_id": session.session_id, "type": "llm", "emotion": emotion, "text": emotion}
        await session.send_text_message(json.dumps(payload, ensure_ascii=False))

    def send_binary_message(self, session: ChatSession, data: bytes) -> None:
        if not session or not session.is_open():
            return
        schedule_coro(session.send_binary_message(data))


__all__ = ["MessageService"]
