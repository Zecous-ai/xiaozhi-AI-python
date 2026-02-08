from __future__ import annotations

from typing import Protocol


class TtsService(Protocol):
    def get_provider_name(self) -> str:
        ...

    def get_voice_name(self) -> str:
        ...

    def get_speed(self) -> float:
        ...

    def get_pitch(self) -> float:
        ...

    def text_to_speech(self, text: str) -> str:
        ...


__all__ = ["TtsService"]
