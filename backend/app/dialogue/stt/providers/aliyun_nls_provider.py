from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("aliyun_nls_stt")


class AliyunNlsSttService:
    def __init__(self, config: dict, token_service) -> None:
        self.config = config or {}
        self.token_service = token_service
        self.api_url = self.config.get("apiUrl")

    def get_provider_name(self) -> str:
        return "aliyun-nls"

    def supports_streaming(self) -> bool:
        return True

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        return self._http_recognition(audio_data)

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        data = b"".join(list(audio_stream))
        return self.recognition(data)

    def _http_recognition(self, audio_data: bytes) -> str:
        if not self.api_url:
            logger.error("Aliyun NLS 未配置 apiUrl")
            return ""
        try:
            token = self.token_service.get_token() if self.token_service else None
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            files = {"file": ("audio.pcm", audio_data, "application/octet-stream")}
            resp = httpx.post(self.api_url, headers=headers, files=files, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("text") or payload.get("result") or ""
        except Exception as exc:
            logger.error("Aliyun NLS 识别失败: %s", exc)
            return ""


__all__ = ["AliyunNlsSttService"]
