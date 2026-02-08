from __future__ import annotations

import logging

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("minimax_tts")


class MiniMaxTtsService:
    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "minimax"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    def text_to_speech(self, text: str) -> str:
        logger.warning("MiniMax TTS 暂未实现，使用 Edge TTS 回退")
        return self._fallback.text_to_speech(text)


__all__ = ["MiniMaxTtsService"]
