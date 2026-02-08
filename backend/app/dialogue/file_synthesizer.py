from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.dialogue.thread_synthesizer import ThreadSynthesizer
from app.utils.async_utils import schedule_coro

logger = logging.getLogger("file_synthesizer")


class FileSynthesizer(ThreadSynthesizer):
    def __init__(self, session, message_service, tts_service, player) -> None:
        self.message_service = message_service
        self.tts_service = tts_service
        super().__init__(session, player)

    def do_synthesize(self, sentence) -> None:
        if self.is_aborted():
            return
        text = sentence.get_text_for_speech()
        try:
            audio_path = self.tts_service.text_to_speech(text)
            sentence.end_synthesis = datetime.utcnow()
            if audio_path:
                sentence.set_audio(Path(audio_path))
            if self.is_aborted():
                return
            if self.session.synthesizer is not self:
                return
            self.player.append(sentence)
            self.player.play()
        except Exception as exc:
            logger.error(
                "TTS任务失败 - seq=%s provider=%s voice=%s reason=%s",
                sentence.seq,
                getattr(self.tts_service, "get_provider_name", lambda: "unknown")(),
                getattr(self.tts_service, "get_voice_name", lambda: "")(),
                exc,
            )
            self._handle_tts_failure(sentence, str(exc))

    def _handle_tts_failure(self, sentence, reason: str) -> None:
        if self.is_aborted():
            return
        sentence.retry_count += 1
        sentence.is_retry = True
        schedule_coro(self.message_service.send_emotion(self.session, "happy"))

        if sentence.retry_count <= settings.tts_max_retry_count:
            logger.info(
                "TTS重试 - seq=%s retry=%s/%s text=%s reason=%s",
                sentence.seq,
                sentence.retry_count,
                settings.tts_max_retry_count,
                sentence.text,
                reason,
            )
            time.sleep(settings.tts_retry_delay_ms / 1000.0)
            self.do_synthesize(sentence)
            return

        logger.error(
            "TTS失败 - seq=%s 重试次数已达上限 reason=%s",
            sentence.seq,
            reason,
        )
