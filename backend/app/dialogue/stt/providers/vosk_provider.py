from __future__ import annotations

import json
import logging
from typing import Optional

from vosk import Model, KaldiRecognizer

from app.core.config import settings
from app.dialogue.stt.base import AudioStream, SttService
from app.utils.audio_constants import SAMPLE_RATE

logger = logging.getLogger("vosk_stt")


class VoskSttService:
    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path or settings.vosk_model_path
        self._model: Optional[Model] = None

    def get_provider_name(self) -> str:
        return "vosk"

    def _load_model(self) -> Model:
        if self._model is None:
            self._model = Model(self.model_path)
        return self._model

    def supports_streaming(self) -> bool:
        return True

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        recognizer = KaldiRecognizer(self._load_model(), SAMPLE_RATE)
        recognizer.AcceptWaveform(audio_data)
        result = json.loads(recognizer.FinalResult() or "{}")
        return result.get("text", "")

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        recognizer = KaldiRecognizer(self._load_model(), SAMPLE_RATE)
        for chunk in audio_stream:
            recognizer.AcceptWaveform(chunk)
        result = json.loads(recognizer.FinalResult() or "{}")
        return result.get("text", "")


__all__ = ["VoskSttService"]
