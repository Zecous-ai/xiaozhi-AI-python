from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.dialogue.device_mcp import DeviceMcpHolder
from app.dialogue.stt.base import AudioStream
from app.utils.audio_constants import AUDIO_PATH

logger = logging.getLogger("session_manager")


class ChatSession:
    ATTR_FIRST_MODEL_RESPONSE_TIME = "firstModelResponseTime"
    ATTR_FIRST_TTS_RESPONSE_TIME = "firstTtsResponseTime"

    def __init__(self, session_id: str, websocket) -> None:
        self.session_id = session_id
        self.websocket = websocket
        self.sys_device: Optional[dict] = None
        self.sys_role_list: Optional[List[dict]] = None
        self.conversation = None
        self.synthesizer = None
        self.iot_descriptors: Dict[str, dict] = {}
        self.tools_session_holder = None
        self.close_after_chat = False
        self.music_playing = False
        self.playing = False
        self.in_wakeup_response = False
        self.mode: Optional[str] = None
        self.audio_stream: Optional[AudioStream] = None
        self.streaming_state = False
        self.last_activity_time = time.time()
        self.support_function_call = True
        self.attributes: Dict[str, object] = {}
        self.device_mcp_holder = DeviceMcpHolder()
        self.player = None
        self.assistant_time_millis: Optional[int] = None

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

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def get_attribute(self, key: str) -> object:
        return self.attributes.get(key)

    def set_assistant_time_millis(self, value: int) -> None:
        self.assistant_time_millis = value
        self.set_attribute("assistantTimeMillis", value)

    def get_assistant_time_millis(self) -> Optional[int]:
        return self.assistant_time_millis

    def get_audio_path(self, who: str, time_millis: int) -> Path:
        instant = datetime.fromtimestamp(time_millis / 1000.0)
        datetime_str = instant.isoformat(timespec="seconds").replace(":", "")
        device_id = (self.sys_device or {}).get("deviceId", "").replace(":", "-")
        role_id = str((self.sys_device or {}).get("roleId", "unknown"))
        extension = "wav" if who == "user" else "opus"
        filename = f"{datetime_str}-{who}.{extension}"
        audio_root = settings.audio_path or AUDIO_PATH
        return Path(audio_root) / device_id / role_id / filename

    def get_tool_callbacks(self) -> List:
        if not self.tools_session_holder:
            return []
        return self.tools_session_holder.get_all_functions()


class SessionManager:
    def __init__(self) -> None:
        self.sessions: Dict[str, ChatSession] = {}
        self.device_index: Dict[str, str] = {}
        self.captcha_state: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self.dialogue_service = None
        self.device_service = None

    def configure(self, dialogue_service=None, device_service=None) -> None:
        self.dialogue_service = dialogue_service
        self.device_service = device_service

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
        logger.info("会话已注册: %s", session_id)

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self.sessions.pop(session_id, None)
            stale_devices = [device_id for device_id, sid in self.device_index.items() if sid == session_id]
            for device_id in stale_devices:
                self.device_index.pop(device_id, None)

    def close_session(self, session: ChatSession | str) -> None:
        if isinstance(session, str):
            session_obj = self.sessions.get(session)
        else:
            session_obj = session
        if not session_obj:
            return
        try:
            if session_obj.websocket is not None:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(session_obj.close())
                except RuntimeError:
                    asyncio.run(session_obj.close())
            if session_obj.audio_stream:
                session_obj.audio_stream.close()
            session_obj.streaming_state = False
            session_obj.audio_stream = None
            if session_obj.conversation:
                session_obj.conversation.clear()
        except Exception as exc:
            logger.error("清理会话资源失败: %s", exc)
        finally:
            self.remove_session(session_obj.session_id)

    def register_device(self, session_id: str, device: dict) -> None:
        session = self.sessions.get(session_id)
        if session is None:
            return
        session.sys_device = device
        device_id = device.get("deviceId") or device.get("device_id")
        if device_id:
            self.device_index[device_id] = session_id
        self.update_last_activity(session_id)

    def get_session_by_device_id(self, device_id: str) -> Optional[ChatSession]:
        session_id = self.device_index.get(device_id)
        if not session_id:
            return None
        return self.sessions.get(session_id)

    def get_device_config(self, session_id: str) -> Optional[dict]:
        session = self.sessions.get(session_id)
        if session:
            return session.sys_device
        return None

    def update_last_activity(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.last_activity_time = time.time()

    def set_close_after_chat(self, session_id: str, close: bool) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.close_after_chat = close

    def is_close_after_chat(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        return bool(session and session.close_after_chat)

    def set_streaming_state(self, session_id: str, state: bool) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.streaming_state = state
        self.update_last_activity(session_id)

    def is_streaming(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        return bool(session and session.streaming_state)

    def set_mode(self, session_id: str, mode: Optional[str]) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.mode = mode

    def get_mode(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        return session.mode if session else None

    def create_audio_stream(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.audio_stream = AudioStream()

    def get_audio_stream(self, session_id: str) -> Optional[AudioStream]:
        session = self.sessions.get(session_id)
        return session.audio_stream if session else None

    def send_audio_data(self, session_id: str, data: bytes) -> None:
        stream = self.get_audio_stream(session_id)
        if stream:
            stream.put(data)

    def complete_audio_stream(self, session_id: str) -> None:
        stream = self.get_audio_stream(session_id)
        if stream:
            stream.close()

    def close_audio_stream(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.audio_stream = None

    def mark_captcha_generation(self, device_id: str) -> bool:
        if device_id in self.captcha_state:
            return False
        self.captcha_state[device_id] = True
        return True

    def unmark_captcha_generation(self, device_id: str) -> None:
        self.captcha_state.pop(device_id, None)

    def check_inactive_sessions(self) -> None:
        if not settings.check_inactive_session:
            return
        now = time.time()
        for session_id, session in list(self.sessions.items()):
            if session.websocket is None:
                continue
            if now - session.last_activity_time > settings.inactive_timeout_seconds:
                if self.dialogue_service:
                    try:
                        self.dialogue_service.send_timeout_message(session)
                    except Exception:
                        self.close_session(session)
                else:
                    self.close_session(session)


session_manager = SessionManager()

__all__ = ["ChatSession", "SessionManager", "session_manager"]
