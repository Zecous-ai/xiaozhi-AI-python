from __future__ import annotations

import asyncio
import threading
import time
from typing import Dict, Optional

from app.core.config import settings


class ChatSession:
    def __init__(self, session_id: str, websocket):
        self.session_id = session_id
        self.websocket = websocket
        self.sys_device: Optional[dict] = None
        self.last_activity_time = time.time()
        self.audio_buffer: bytearray = bytearray()
        self.streaming_state = False
        self.mode: Optional[str] = None
        self.close_after_chat = False
        self.in_wakeup_response = False

    def is_open(self) -> bool:
        return self.websocket is not None

    async def send_text_message(self, message: str) -> None:
        if self.websocket is None:
            return
        await self.websocket.send_text(message)

    async def send_binary_message(self, data: bytes) -> None:
        if self.websocket is None:
            return
        await self.websocket.send_bytes(data)

    async def close(self) -> None:
        if self.websocket is None:
            return
        try:
            await self.websocket.close()
        finally:
            self.websocket = None


class SessionManager:
    def __init__(self) -> None:
        self.sessions: Dict[str, ChatSession] = {}
        self.device_index: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start_background_tasks(self) -> None:
        if not settings.check_inactive_session:
            return
        if self._thread and self._thread.is_alive():
            return

        def _loop():
            while not self._stop:
                self.check_inactive_sessions()
                time.sleep(10)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_background_tasks(self) -> None:
        self._stop = True
        if self._thread:
            self._thread.join(timeout=5)

    def register_session(self, session_id: str, session: ChatSession) -> None:
        with self._lock:
            self.sessions[session_id] = session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self.sessions.pop(session_id, None)

    def register_device(self, session_id: str, device: dict) -> None:
        session = self.sessions.get(session_id)
        if session is None:
            return
        session.sys_device = device
        device_id = device.get("deviceId") or device.get("device_id")
        if device_id:
            self.device_index[device_id] = session_id

    def get_session_by_device_id(self, device_id: str) -> Optional[ChatSession]:
        session_id = self.device_index.get(device_id)
        if not session_id:
            return None
        return self.sessions.get(session_id)

    def update_last_activity(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.last_activity_time = time.time()

    def set_streaming_state(self, session_id: str, state: bool) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.streaming_state = state

    def is_streaming(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        return bool(session and session.streaming_state)

    def append_audio(self, session_id: str, data: bytes) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.audio_buffer.extend(data)

    def pop_audio(self, session_id: str) -> bytes:
        session = self.sessions.get(session_id)
        if session is None:
            return b""
        data = bytes(session.audio_buffer)
        session.audio_buffer.clear()
        return data

    def check_inactive_sessions(self) -> None:
        if not settings.check_inactive_session:
            return
        now = time.time()
        for session_id, session in list(self.sessions.items()):
            if session.websocket is None:
                continue
            if now - session.last_activity_time > settings.inactive_timeout_seconds:
                asyncio.run(self._close_due_to_timeout(session))

    async def _close_due_to_timeout(self, session: ChatSession) -> None:
        try:
            await session.send_text_message('{"type":"tts","state":"stop","text":"会话超时"}')
            await session.close()
        finally:
            self.remove_session(session.session_id)


session_manager = SessionManager()

__all__ = ["ChatSession", "SessionManager", "session_manager"]
