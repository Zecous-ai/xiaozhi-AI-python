from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from threading import Event, Lock, Thread
from urllib.parse import urlencode

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("tencent_stt")


class TencentSttService:
    WS_HOST = "asr.cloud.tencent.com"
    WS_PATH = "/asr/v2"
    RECOGNITION_TIMEOUT_SECONDS = 90

    def __init__(self, config: dict) -> None:
        self.config = config or {}
        self.secret_id = self.config.get("ak") or self.config.get("apiKey")
        self.secret_key = self.config.get("sk") or self.config.get("apiSecret")
        self.app_id = self.config.get("appId")
        self.region = self.config.get("region") or "ap-shanghai"
        self.model = self.config.get("configName") or "16k_zh"

    def get_provider_name(self) -> str:
        return "tencent"

    def supports_streaming(self) -> bool:
        return True

    def recognition(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        stream = AudioStream()
        stream.put(audio_data)
        stream.close()
        return self.stream_recognition(stream)

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        from websocket import WebSocketTimeoutException, create_connection

        if not self.secret_id or not self.secret_key or not self.app_id:
            logger.error("Tencent STT missing appId/secretId/secretKey")
            return ""

        ws = None
        done = Event()
        failed = Event()
        lock = Lock()
        final_text = ""
        partial_text = ""

        try:
            ws = create_connection(self._build_ws_url(), timeout=10, enable_multithread=True)
            ws.settimeout(1)

            def _receiver() -> None:
                nonlocal final_text, partial_text
                while not done.is_set():
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        continue
                    except Exception as exc:
                        logger.error("Tencent STT receive failed: %s", exc)
                        failed.set()
                        done.set()
                        return

                    if isinstance(message, bytes):
                        message = message.decode("utf-8", errors="ignore")
                    if not message:
                        continue

                    try:
                        payload = json.loads(message)
                    except json.JSONDecodeError:
                        logger.warning("Tencent STT non-JSON message: %s", message)
                        continue

                    code = int(payload.get("code", 0))
                    if code != 0:
                        logger.error("Tencent STT error: code=%s message=%s", code, payload.get("message"))
                        failed.set()
                        done.set()
                        return

                    result = payload.get("result") or {}
                    text = result.get("voice_text_str") or ""
                    if text:
                        with lock:
                            if int(result.get("slice_type", -1)) == 2:
                                final_text = text
                            else:
                                partial_text = text

                    if int(payload.get("final", 0)) == 1:
                        with lock:
                            if not final_text and partial_text:
                                final_text = partial_text
                        done.set()
                        return

            Thread(target=_receiver, daemon=True).start()

            for chunk in audio_stream:
                if not chunk:
                    continue
                ws.send_binary(chunk)

            ws.send(json.dumps({"type": "end"}, ensure_ascii=False))
            if not done.wait(self.RECOGNITION_TIMEOUT_SECONDS):
                logger.warning("Tencent STT stream timeout")
        except Exception as exc:
            logger.error("Tencent STT stream failed: %s", exc)
            failed.set()
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

        with lock:
            result = final_text or partial_text
        if failed.is_set() and not result:
            return ""
        return result

    def _build_ws_url(self) -> str:
        timestamp = int(time.time())
        params = {
            "engine_model_type": self.model,
            "expired": str(timestamp + 24 * 60 * 60),
            "nonce": str(int(time.time() * 1000) % 1000000),
            "secretid": self.secret_id,
            "timestamp": str(timestamp),
            "voice_format": "1",
            "voice_id": str(uuid.uuid4()),
        }

        sorted_query = "&".join(f"{key}={params[key]}" for key in sorted(params))
        sign_source = f"{self.WS_HOST}{self.WS_PATH}/{self.app_id}?{sorted_query}"
        digest = hmac.new(self.secret_key.encode("utf-8"), sign_source.encode("utf-8"), hashlib.sha1).digest()
        params["signature"] = base64.b64encode(digest).decode("utf-8")

        return f"wss://{self.WS_HOST}{self.WS_PATH}/{self.app_id}?{urlencode(params)}"


__all__ = ["TencentSttService"]
