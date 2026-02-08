from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime
from typing import List, Optional

from app.communication.session import ChatSession, session_manager
from app.dialogue.file_player import FilePlayer
from app.dialogue.file_synthesizer import FileSynthesizer
from app.dialogue.intent_detector import IntentDetector, UserIntent
from app.dialogue.llm.chat_service import ChatService
from app.dialogue.message_service import MessageService
from app.dialogue.stt.factory import SttServiceFactory
from app.dialogue.tts.factory import TtsServiceFactory
from app.dialogue.memory import ChatMessage, ChatMemory
from app.dialogue.vad.vad_service import VadService, VadStatus
from app.services.config_service import SysConfigService
from app.services.role_service import SysRoleService
from app.services.sys_message_service import SysMessageService
from app.utils.audio_utils import save_as_wav
from app.utils.async_utils import schedule_coro

logger = logging.getLogger("dialogue_service")

GOODBYE_MESSAGES = [
    "好的，拜拜~有需要随时叫我哦~",
    "好呀，那我先走啦，拜拜~",
    "收到！我先退下啦，有需要再叫我~",
    "明白！那我先不打扰你啦，拜拜~",
    "好的呢，有事随时呼叫我，拜拜~",
    "好呀，我先去休息一下，需要我时再叫我哦~",
    "收到！那我就先告退啦，拜拜~",
    "好的，我先离开啦，有问题随时找我~",
    "明白！我先下线休息了，需要时再唤醒我~",
    "好呀好呀，那我先走啦，回见~",
]

TIMEOUT_MESSAGES = [
    "你好像在忙别的事情，我先退下啦~",
    "看来你暂时不需要我了，我先休息一会～",
    "你有一会儿没说话了，我先去充电啦~",
    "看起来你在忙，我先不打扰啦",
    "看来你有别的事情要忙，我先离开啦~",
    "你有段时间没说话了，我先去休息了~",
]


class DialogueService:
    def __init__(
        self,
        config_service: SysConfigService,
        role_service: SysRoleService,
        message_service: MessageService,
        sys_message_service: SysMessageService,
        vad_service: VadService,
        stt_factory: SttServiceFactory,
        tts_factory: TtsServiceFactory,
        chat_service: ChatService,
        intent_detector: IntentDetector,
    ) -> None:
        self.config_service = config_service
        self.role_service = role_service
        self.message_service = message_service
        self.sys_message_service = sys_message_service
        self.vad_service = vad_service
        self.stt_factory = stt_factory
        self.tts_factory = tts_factory
        self.chat_service = chat_service
        self.intent_detector = intent_detector

    def process_audio_data(self, session: ChatSession, opus_data: bytes) -> None:
        if session is None or not opus_data:
            return
        session_id = session.session_id
        if session.in_wakeup_response or session.close_after_chat:
            return
        device = session.sys_device or {}
        if not device.get("roleId"):
            return
        role = self.role_service.select_role_by_id(int(device.get("roleId")))
        if not role:
            return
        stt_config = self.config_service.select_config_by_id(int(role.get("sttId"))) if role.get("sttId") else None

        vad_result = self.vad_service.process_audio(session_id, opus_data)
        if not vad_result or vad_result.status == VadStatus.ERROR or vad_result.data is None:
            return
        session_manager.update_last_activity(session_id)

        if vad_result.status == VadStatus.SPEECH_START:
            if session.synthesizer and session.synthesizer.is_dialog():
                self.abort_dialogue(session, "检测到vad")
            self._start_stt(session, session_id, stt_config, device, vad_result.data)
        elif vad_result.status == VadStatus.SPEECH_CONTINUE:
            if session_manager.is_streaming(session_id):
                session_manager.send_audio_data(session_id, vad_result.data)
        elif vad_result.status == VadStatus.SPEECH_END:
            if session_manager.is_streaming(session_id):
                session_manager.complete_audio_stream(session_id)
                session_manager.set_streaming_state(session_id, False)

    def _start_stt(self, session: ChatSession, session_id: str, stt_config: Optional[dict], device: dict, initial_audio: bytes) -> None:
        def _task() -> None:
            try:
                session_manager.close_audio_stream(session_id)
                session_manager.create_audio_stream(session_id)
                session_manager.set_streaming_state(session_id, True)

                stt_service = self.stt_factory.get_stt_service(stt_config)
                if not stt_service:
                    return

                if initial_audio:
                    session_manager.send_audio_data(session_id, initial_audio)

                audio_stream = session_manager.get_audio_stream(session_id)
                if not audio_stream:
                    return
                final_text = stt_service.stream_recognition(audio_stream)
                if not final_text:
                    return

                schedule_coro(self.message_service.send_stt_message(session, final_text))
                schedule_coro(self.message_service.send_tts_message(session, None, "start"))

                pcm_frames = self.vad_service.get_pcm_data(session_id)
                user_message = self._save_user_audio(session, pcm_frames, final_text)

                assistant_time_millis = int(time.time() * 1000)
                session.set_assistant_time_millis(assistant_time_millis)

                intent = self.intent_detector.detect_intent(final_text)
                if intent and intent.type == "EXIT":
                    self.handle_intent(session, intent)
                    return

                token_stream = self.chat_service.chat_stream(session, user_message, True)
                synthesizer = self._init_synthesizer(session)
                synthesizer.start_synthesis(token_stream)
            except Exception as exc:
                logger.error("流式识别失败: %s", exc)

        threading.Thread(target=_task, daemon=True).start()

    async def handle_text(self, session: ChatSession, text: str) -> None:
        if not text:
            return
        device = session.sys_device or {}
        role_id = device.get("roleId")
        if not role_id:
            await self.message_service.send_tts_message(session, "设备未绑定角色，请到角色配置页面完成配置后开始对话", "stop")
            return
        role = self.role_service.select_role_by_id(int(role_id))
        if not role:
            await self.message_service.send_tts_message(session, "角色不存在", "stop")
            return
        session_manager.update_last_activity(session.session_id)
        await self.message_service.send_stt_message(session, text)
        await self.message_service.send_tts_message(session, None, "start")

        user_message = self._save_user_audio(session, [], text)
        assistant_time_millis = int(time.time() * 1000)
        session.set_assistant_time_millis(assistant_time_millis)

        intent = self.intent_detector.detect_intent(text)
        if intent and intent.type == "EXIT":
            self.handle_intent(session, intent)
            return

        token_stream = self.chat_service.chat_stream(session, user_message, True)
        synthesizer = self._init_synthesizer(session)
        synthesizer.start_synthesis(token_stream)

    async def handle_wake_word(self, session: ChatSession, text: str) -> None:
        session.in_wakeup_response = True
        device = session.sys_device or {}
        if not device:
            return
        if session.assistant_time_millis is None:
            session.set_assistant_time_millis(int(time.time() * 1000))
        if not session.player:
            session.player = FilePlayer(session, self.message_service, session_manager, self.sys_message_service)
        role = self.role_service.select_role_by_id(int(device.get("roleId"))) if device.get("roleId") else None
        if not role:
            return
        tts_config = self.config_service.select_config_by_id(int(role.get("ttsId"))) if role.get("ttsId") else None
        tts_service = self.tts_factory.get_tts_service(
            tts_config, role.get("voiceName"), float(role.get("ttsPitch") or 1.0), float(role.get("ttsSpeed") or 1.0)
        )
        synthesizer = FileSynthesizer(session, self.message_service, tts_service, session.player)
        session.synthesizer = synthesizer

        await self.message_service.send_stt_message(session, text)
        user_message = self._save_user_audio(session, [], text)
        token_stream = self.chat_service.chat_stream(session, user_message, False)
        synthesizer.start_synthesis(token_stream)

    def handle_intent(self, session: ChatSession, intent: UserIntent) -> None:
        if intent.type == "EXIT":
            self.send_goodbye_message(session)

    def send_goodbye_message(self, session: ChatSession) -> str:
        return self._send_exit_message(session, self._random_goodbye(), "用户主动退出")

    def send_timeout_message(self, session: ChatSession) -> str:
        return self._send_exit_message(session, self._random_timeout(), "会话超时退出")

    def _send_exit_message(self, session: ChatSession, goodbye_message: str, reason: str) -> str:
        _ = reason
        session.close_after_chat = True
        session.set_assistant_time_millis(int(time.time() * 1000))
        schedule_coro(self.message_service.send_tts_message(session, None, "start"))
        synthesizer = self._init_synthesizer(session)
        synthesizer.append_sentence(goodbye_message)
        synthesizer.set_last()
        return goodbye_message

    def abort_dialogue(self, session: ChatSession, reason: Optional[str]) -> None:
        _ = reason
        session_id = session.session_id
        session_manager.close_audio_stream(session_id)
        session_manager.set_streaming_state(session_id, False)

        synthesizer = session.synthesizer
        if synthesizer:
            synthesizer.clear_all_sentences()
            synthesizer.cancel()
            session.synthesizer = None

        player = session.player
        if player:
            player.stop()
        schedule_coro(self.message_service.send_tts_message(session, None, "stop"))

    def cleanup_session(self, session: ChatSession) -> None:
        synthesizer = session.synthesizer
        if synthesizer:
            synthesizer.cancel()
        session.synthesizer = None
        if session.player:
            session.player.stop()

    def _init_synthesizer(self, session: ChatSession):
        device = session.sys_device or {}
        role_id = device.get("roleId")
        role = self.role_service.select_role_by_id(int(role_id)) if role_id else None
        tts_config = self.config_service.select_config_by_id(int(role.get("ttsId"))) if role and role.get("ttsId") else None
        tts_service = self.tts_factory.get_tts_service(
            tts_config,
            (role or {}).get("voiceName") or "zh-CN-XiaoyiNeural",
            float((role or {}).get("ttsPitch") or 1.0),
            float((role or {}).get("ttsSpeed") or 1.0),
        )
        player = session.player
        if player is None:
            player = FilePlayer(session, self.message_service, session_manager, self.sys_message_service)
            session.player = player
        synthesizer = FileSynthesizer(session, self.message_service, tts_service, player)
        session.synthesizer = synthesizer
        return synthesizer

    def _save_user_audio(self, session: ChatSession, pcm_frames: List[bytes], final_text: str) -> ChatMessage:
        user_time_millis = int(time.time() * 1000)
        user_message = ChatMessage(role="user", content=final_text, metadata={})
        ChatMemory.set_time_millis(user_message, user_time_millis)
        audio_path: Optional[str] = None
        if pcm_frames:
            total_size = sum(len(frame) for frame in pcm_frames)
            full_pcm = bytearray(total_size)
            offset = 0
            for frame in pcm_frames:
                full_pcm[offset : offset + len(frame)] = frame
                offset += len(frame)
            try:
                path = session.get_audio_path("user", user_time_millis)
                save_as_wav(path, bytes(full_pcm))
                user_message.metadata[ChatMemory.AUDIO_PATH] = str(path)
                audio_path = str(path)
            except Exception as exc:
                logger.error("保存用户音频失败: %s", exc)

        create_time = self._format_time(user_time_millis)
        device = session.sys_device or {}
        role_id = device.get("roleId")
        self.sys_message_service.add(
            {
                "deviceId": device.get("deviceId"),
                "sessionId": session.session_id,
                "sender": "user",
                "roleId": role_id,
                "message": final_text,
                "messageType": "NORMAL",
                "createTime": create_time,
            }
        )
        if audio_path and device.get("deviceId") and role_id:
            self.sys_message_service.update_message_by_audio_file(device.get("deviceId"), int(role_id), "user", create_time, audio_path)
        return user_message

    @staticmethod
    def _format_time(time_millis: int) -> str:
        return datetime.fromtimestamp(time_millis / 1000.0).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _random_goodbye() -> str:
        return random.choice(GOODBYE_MESSAGES)

    @staticmethod
    def _random_timeout() -> str:
        return random.choice(TIMEOUT_MESSAGES)


__all__ = ["DialogueService"]
