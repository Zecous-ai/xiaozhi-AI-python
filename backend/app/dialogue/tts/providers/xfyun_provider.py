from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from email.utils import formatdate
from urllib.parse import quote

from websocket import create_connection

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("xfyun_tts")


class XfyunTtsService:
    HOST = "tts-api.xfyun.cn"
    PATH = "/v2/tts"

    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self.app_id = self.config.get("appId")
        self.api_key = self.config.get("apiKey")
        self.api_secret = self.config.get("apiSecret")
        self.api_url = self.config.get("apiUrl")
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "xfyun"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    @staticmethod
    def _to_xfyun_value(value: float) -> int:
        mapped = int(round((value - 0.5) * 100 / 1.5))
        return max(0, min(100, mapped))

    def _build_ws_url(self) -> str:
        if self.api_url:
            return self.api_url
        date = formatdate(timeval=time.time(), localtime=False, usegmt=True)
        signature_origin = f"host: {self.HOST}\ndate: {date}\nGET {self.PATH} HTTP/1.1"
        signature_sha = hmac.new(self.api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode("utf-8")
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
        return (
            f"wss://{self.HOST}{self.PATH}"
            f"?authorization={quote(authorization)}"
            f"&date={quote(date)}"
            f"&host={self.HOST}"
        )

    def _build_payload(self, text: str) -> dict:
        return {
            "common": {"app_id": self.app_id},
            "business": {
                "aue": "lame",
                "auf": "audio/L16;rate=16000",
                "vcn": self.voice_name,
                "tte": "UTF8",
                "speed": self._to_xfyun_value(self.speed),
                "pitch": self._to_xfyun_value(self.pitch),
            },
            "data": {
                "status": 2,
                "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            },
        }

    def _synthesize(self, text: str) -> bytes:
        ws = create_connection(self._build_ws_url(), timeout=30, enable_multithread=True)
        try:
            ws.send(json.dumps(self._build_payload(text), ensure_ascii=False))
            chunks: list[bytes] = []
            while True:
                message = ws.recv()
                if isinstance(message, bytes):
                    message = message.decode("utf-8", errors="ignore")
                if not message:
                    continue
                payload = json.loads(message)
                code = int(payload.get("code", -1))
                if code != 0:
                    raise RuntimeError(f"Xfyun TTS failed: code={code}, message={payload.get('message')}")
                data = payload.get("data") or {}
                audio_b64 = data.get("audio")
                if audio_b64:
                    chunks.append(base64.b64decode(audio_b64))
                if int(data.get("status", -1)) == 2:
                    break
            audio_data = b"".join(chunks)
            if not audio_data:
                raise RuntimeError("Xfyun TTS returned empty audio")
            return audio_data
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def text_to_speech(self, text: str) -> str:
        if not text:
            return ""
        if not self.app_id or not self.api_key or not self.api_secret:
            logger.warning("Xfyun TTS missing appId/apiKey/apiSecret, fallback to Edge")
            return self._fallback.text_to_speech(text)

        try:
            audio_data = self._synthesize(text)
            os.makedirs(self.output_path, exist_ok=True)
            out_path = os.path.join(self.output_path, f"{uuid.uuid4().hex}.mp3").replace("\\", "/")
            with open(out_path, "wb") as file:
                file.write(audio_data)
            return out_path
        except Exception as exc:
            logger.error("Xfyun TTS error, fallback to Edge: %s", exc)
            return self._fallback.text_to_speech(text)


__all__ = ["XfyunTtsService"]
