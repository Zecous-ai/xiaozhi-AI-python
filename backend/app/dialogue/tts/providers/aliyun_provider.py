from __future__ import annotations

import logging
import os
import uuid

try:
    import dashscope  # type: ignore
except Exception:  # pragma: no cover
    dashscope = None

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("aliyun_tts")


class AliyunTtsService:
    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "aliyun"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    def text_to_speech(self, text: str) -> str:
        if dashscope is None:
            logger.warning("dashscope package missing, fallback to Edge")
            return self._fallback.text_to_speech(text)

        api_key = self.config.get("apiKey")
        if not api_key:
            logger.warning("Aliyun TTS missing apiKey, fallback to Edge")
            return self._fallback.text_to_speech(text)

        try:
            dashscope.api_key = api_key
            result = dashscope.SpeechSynthesizer.call(
                model=self.voice_name,
                text=text,
                format="wav",
                sample_rate=16000,
                rate=float(self.speed),
                pitch=float(self.pitch),
            )
            audio_data = None
            if result is not None:
                audio_data = result.get_audio_data()

            if not audio_data:
                logger.error("Aliyun TTS returned empty audio, fallback to Edge")
                return self._fallback.text_to_speech(text)

            os.makedirs(self.output_path, exist_ok=True)
            out_path = os.path.join(self.output_path, f"{uuid.uuid4().hex}.wav").replace("\\", "/")
            with open(out_path, "wb") as f:
                f.write(audio_data)
            return out_path
        except Exception as exc:
            logger.error("Aliyun TTS error, fallback to Edge: %s", exc)
            return self._fallback.text_to_speech(text)


__all__ = ["AliyunTtsService"]
