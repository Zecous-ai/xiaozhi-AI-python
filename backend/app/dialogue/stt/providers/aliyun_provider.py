from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.dialogue.stt.base import AudioStream, SttService
from app.utils.audio_constants import SAMPLE_RATE

logger = logging.getLogger("aliyun_stt")


class AliyunSttService:
    def __init__(self, config: dict) -> None:
        self.api_key = config.get("apiKey") if config else None
        self.model = (config.get("configName") or "").strip() if config else ""
        self.api_url = config.get("apiUrl") if config else None

    def get_provider_name(self) -> str:
        return "aliyun"

    def supports_streaming(self) -> bool:
        return True

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        # 优先使用 DashScope SDK（如已安装）
        try:
            import dashscope  # type: ignore
            from dashscope.audio.asr import Recognition  # type: ignore

            dashscope.api_key = self.api_key
            recognition = Recognition(model=self.model or "paraformer-realtime-v2", format="pcm", sample_rate=SAMPLE_RATE)
            result = recognition.call(audio_data)
            if isinstance(result, dict):
                return (
                    result.get("output", {}).get("text")
                    or result.get("output", {}).get("sentence", "")
                    or result.get("text", "")
                )
        except Exception as exc:
            logger.warning("DashScope 识别失败，降级为 HTTP: %s", exc)

        return self._http_recognition(audio_data)

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        data = b"".join(list(audio_stream))
        return self.recognition(data)

    def _http_recognition(self, audio_data: bytes) -> str:
        if not self.api_url:
            logger.error("Aliyun STT 未配置 apiUrl")
            return ""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            files = {"file": ("audio.pcm", audio_data, "application/octet-stream")}
            resp = httpx.post(self.api_url, headers=headers, files=files, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            return (
                payload.get("text")
                or payload.get("result")
                or payload.get("output", {}).get("text")
                or ""
            )
        except Exception as exc:
            logger.error("Aliyun STT HTTP 调用失败: %s", exc)
            return ""


__all__ = ["AliyunSttService"]
