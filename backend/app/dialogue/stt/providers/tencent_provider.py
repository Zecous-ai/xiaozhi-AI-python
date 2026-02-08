from __future__ import annotations

import base64
import logging
from typing import Optional

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("tencent_stt")


class TencentSttService:
    def __init__(self, config: dict) -> None:
        self.config = config or {}
        self.secret_id = self.config.get("ak") or self.config.get("apiKey")
        self.secret_key = self.config.get("sk") or self.config.get("apiSecret")
        self.region = self.config.get("region") or "ap-shanghai"
        self.model = self.config.get("configName") or "16k_zh"

    def get_provider_name(self) -> str:
        return "tencent"

    def supports_streaming(self) -> bool:
        return False

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        try:
            from tencentcloud.common import credential  # type: ignore
            from tencentcloud.asr.v20190614 import asr_client, models  # type: ignore

            cred = credential.Credential(self.secret_id, self.secret_key)
            client = asr_client.AsrClient(cred, self.region)
            req = models.SentenceRecognitionRequest()
            req.EngineModelType = self.model
            req.SourceType = 1
            req.VoiceFormat = "pcm"
            req.Data = base64.b64encode(audio_data).decode("ascii")
            resp = client.SentenceRecognition(req)
            return getattr(resp, "Result", "") or ""
        except Exception as exc:
            logger.error("腾讯 STT 识别失败: %s", exc)
            return ""

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        data = b"".join(list(audio_stream))
        return self.recognition(data)


__all__ = ["TencentSttService"]
