from __future__ import annotations

import base64
import logging
import os
import uuid

import httpx

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("volcengine_tts")


class VolcengineTtsService:
    API_URL = "https://openspeech.bytedance.com/api/v1/tts"

    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "volcengine"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    def _build_payload(self, text: str, app_id: str, token: str) -> dict:
        return {
            "app": {
                "appid": app_id,
                "token": token,
                "cluster": "volcano_tts",
            },
            "user": {"uid": str(uuid.uuid4())},
            "audio": {
                "voice_type": self.voice_name,
                "encoding": "wav",
                "speed_ratio": self.speed,
                "volume_ratio": 1.0,
                "pitch_ratio": self.pitch,
                "rate": 16000,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson",
            },
        }

    def text_to_speech(self, text: str) -> str:
        app_id = self.config.get("appId")
        token = self.config.get("apiKey")
        if not app_id or not token:
            logger.warning("Volcengine TTS missing appId/apiKey, fallback to Edge")
            return self._fallback.text_to_speech(text)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer; {token}",
        }
        payload = self._build_payload(text, app_id, token)

        try:
            response = httpx.post(self.API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Java implementation expects code=3000.
            if data.get("code") != 3000:
                logger.error("Volcengine TTS failed: %s", data)
                return self._fallback.text_to_speech(text)

            audio_b64 = data.get("data")
            if not audio_b64:
                logger.error("Volcengine TTS missing audio data")
                return self._fallback.text_to_speech(text)

            audio_bytes = base64.b64decode(audio_b64)
            os.makedirs(self.output_path, exist_ok=True)
            out_path = os.path.join(self.output_path, f"{uuid.uuid4().hex}.wav").replace("\\", "/")
            with open(out_path, "wb") as f:
                f.write(audio_bytes)
            return out_path
        except Exception as exc:
            logger.error("Volcengine TTS error, fallback to Edge: %s", exc)
            return self._fallback.text_to_speech(text)


__all__ = ["VolcengineTtsService"]
