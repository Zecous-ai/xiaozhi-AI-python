from __future__ import annotations

import logging
import os
import uuid

import httpx

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("minimax_tts")


class MiniMaxTtsService:
    API_URL = "https://api.minimaxi.com/v1/t2a_v2"

    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "minimax"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    def _build_payload(self, text: str) -> dict:
        # Map pitch from [0.5, 2.0] to minimax [-12, 12]
        minimax_pitch = int(round((self.pitch - 1.0) * 24))
        minimax_pitch = max(-12, min(12, minimax_pitch))

        return {
            "model": "speech-02-hd",
            "text": text,
            "stream": False,
            "stream_options": {"exclude_aggregated_audio": True},
            "language_boost": "auto",
            "output_format": "hex",
            "voice_setting": {
                "voice_id": self.voice_name,
                "speed": self.speed,
                "vol": 1,
                "pitch": minimax_pitch,
                "emotion": "happy",
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
            },
        }

    def text_to_speech(self, text: str) -> str:
        group_id = self.config.get("appId")
        api_key = self.config.get("apiKey")
        if not group_id or not api_key:
            logger.warning("MiniMax TTS missing appId/apiKey, fallback to Edge")
            return self._fallback.text_to_speech(text)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = self._build_payload(text)
        url = f"{self.API_URL}?Groupid={group_id}"

        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            base_resp = data.get("base_resp") or {}
            if base_resp.get("status_code") != 0:
                logger.error("MiniMax TTS failed: %s", base_resp)
                return self._fallback.text_to_speech(text)

            audio_hex = (data.get("data") or {}).get("audio")
            if not audio_hex:
                logger.error("MiniMax TTS missing audio field")
                return self._fallback.text_to_speech(text)

            audio_bytes = bytes.fromhex(audio_hex)
            os.makedirs(self.output_path, exist_ok=True)
            out_path = os.path.join(self.output_path, f"{uuid.uuid4().hex}.mp3").replace("\\", "/")
            with open(out_path, "wb") as f:
                f.write(audio_bytes)
            return out_path
        except Exception as exc:
            logger.error("MiniMax TTS error, fallback to Edge: %s", exc)
            return self._fallback.text_to_speech(text)


__all__ = ["MiniMaxTtsService"]
