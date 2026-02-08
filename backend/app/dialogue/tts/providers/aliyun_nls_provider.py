from __future__ import annotations

import logging
import os
import uuid

import httpx

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("aliyun_nls_tts")


class AliyunNlsTtsService:
    DEFAULT_API_URL = "https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/tts"

    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str, token_service) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self.token_service = token_service
        self.app_key = self.config.get("apiKey")
        self.api_url = self.config.get("apiUrl") or self.DEFAULT_API_URL
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "aliyun-nls"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    @staticmethod
    def _to_nls_value(value: float) -> int:
        mapped = int(round((value - 1.0) * 500))
        return max(-500, min(500, mapped))

    def _build_payload(self, text: str) -> dict:
        return {
            "appkey": self.app_key,
            "text": text,
            "format": "wav",
            "sample_rate": 16000,
            "voice": self.voice_name,
            "volume": 100,
            "speech_rate": self._to_nls_value(self.speed),
            "pitch_rate": self._to_nls_value(self.pitch),
        }

    def _synthesize(self, text: str) -> bytes:
        token = self.token_service.get_token() if self.token_service else None
        if not token:
            raise RuntimeError("Aliyun NLS token unavailable")

        headers = {
            "Content-Type": "application/json",
            "X-NLS-Token": token,
        }
        response = httpx.post(self.api_url, json=self._build_payload(text), headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Aliyun NLS request failed: {response.status_code} {response.text}")

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            raise RuntimeError(f"Aliyun NLS returned error: {response.text}")

        if not response.content:
            raise RuntimeError("Aliyun NLS returned empty audio")
        return response.content

    def text_to_speech(self, text: str) -> str:
        if not text:
            return ""
        if not self.app_key:
            logger.warning("Aliyun NLS TTS missing apiKey(appKey), fallback to Edge")
            return self._fallback.text_to_speech(text)

        try:
            audio_data = self._synthesize(text)
            os.makedirs(self.output_path, exist_ok=True)
            out_path = os.path.join(self.output_path, f"{uuid.uuid4().hex}.wav").replace("\\", "/")
            with open(out_path, "wb") as file:
                file.write(audio_data)
            return out_path
        except Exception as exc:
            logger.error("Aliyun NLS TTS error, fallback to Edge: %s", exc)
            return self._fallback.text_to_speech(text)


__all__ = ["AliyunNlsTtsService"]
