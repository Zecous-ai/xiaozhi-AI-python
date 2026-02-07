from __future__ import annotations

import os
import uuid

import edge_tts

from app.core.config import settings


class EdgeTtsService:
    def __init__(self, voice_name: str, pitch: float = 1.0, speed: float = 1.0) -> None:
        self.voice_name = voice_name
        self.pitch = pitch
        self.speed = speed

    async def text_to_speech(self, text: str) -> str:
        os.makedirs(settings.upload_path, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.mp3"
        out_path = os.path.join(settings.upload_path, filename)
        rate = f"{int((self.speed - 1.0) * 100)}%" if self.speed else "0%"
        pitch = f"{int((self.pitch - 1.0) * 100)}%" if self.pitch else "0%"
        communicate = edge_tts.Communicate(text, self.voice_name, rate=rate, pitch=pitch)
        await communicate.save(out_path)
        return out_path.replace("\\", "/")


__all__ = ["EdgeTtsService"]
