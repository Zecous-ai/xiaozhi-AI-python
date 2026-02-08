from __future__ import annotations

import logging

import httpx

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("funasr_stt")


class FunASRSttService:
    def __init__(self, config: dict) -> None:
        self.config = config or {}
        self.api_url = self.config.get("apiUrl")

    def get_provider_name(self) -> str:
        return "funasr"

    def supports_streaming(self) -> bool:
        return False

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        if not self.api_url:
            logger.error("FunASR 未配置 apiUrl")
            return ""
        try:
            files = {"file": ("audio.pcm", audio_data, "application/octet-stream")}
            resp = httpx.post(self.api_url, files=files, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("text") or payload.get("result") or ""
        except Exception as exc:
            logger.error("FunASR 识别失败: %s", exc)
            return ""

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        data = b"".join(list(audio_stream))
        return self.recognition(data)


__all__ = ["FunASRSttService"]
