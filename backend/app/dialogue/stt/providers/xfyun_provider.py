from __future__ import annotations

import logging

import httpx

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("xfyun_stt")


class XfyunSttService:
    def __init__(self, config: dict) -> None:
        self.config = config or {}
        self.api_url = self.config.get("apiUrl")
        self.api_key = self.config.get("apiKey")
        self.api_secret = self.config.get("apiSecret")
        self.app_id = self.config.get("appId")

    def get_provider_name(self) -> str:
        return "xfyun"

    def supports_streaming(self) -> bool:
        return False

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        if not self.api_url:
            logger.error("讯飞 STT 未配置 apiUrl")
            return ""
        try:
            headers = {}
            if self.api_key:
                headers["X-Api-Key"] = self.api_key
            if self.api_secret:
                headers["X-Api-Secret"] = self.api_secret
            if self.app_id:
                headers["X-App-Id"] = self.app_id
            files = {"file": ("audio.pcm", audio_data, "application/octet-stream")}
            resp = httpx.post(self.api_url, headers=headers, files=files, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("text") or payload.get("result") or ""
        except Exception as exc:
            logger.error("讯飞 STT 识别失败: %s", exc)
            return ""

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        data = b"".join(list(audio_stream))
        return self.recognition(data)


__all__ = ["XfyunSttService"]
