from __future__ import annotations

import os
import uuid

import edge_tts


class EdgeTtsService:
    def __init__(self, voice_name: str, pitch: float = 1.0, speed: float = 1.0, output_path: str = "audio/") -> None:
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path

    def get_provider_name(self) -> str:
        return "edge"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    def text_to_speech(self, text: str) -> str:
        os.makedirs(self.output_path, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.mp3"
        out_path = os.path.join(self.output_path, filename).replace("\\", "/")
        rate = f"{int((self.speed - 1.0) * 100)}%" if self.speed else "0%"
        pitch = f"{int((self.pitch - 1.0) * 100)}%" if self.pitch else "0%"
        communicate = edge_tts.Communicate(text, self.voice_name, rate=rate, pitch=pitch)
        # edge-tts 是异步，这里使用同步封装
        import asyncio

        asyncio.run(communicate.save(out_path))
        return out_path


__all__ = ["EdgeTtsService"]
