from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from email.utils import formatdate
from threading import Event, Lock, Thread
from urllib.parse import quote

import httpx
from websocket import WebSocketTimeoutException, create_connection

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("xfyun_stt")


class XfyunSttService:
    HOST = "iat-api.xfyun.cn"
    PATH = "/v2/iat"
    RECOGNITION_TIMEOUT_SECONDS = 90

    def __init__(self, config: dict) -> None:
        self.config = config or {}
        self.api_url = self.config.get("apiUrl")
        self.api_key = self.config.get("apiKey")
        self.api_secret = self.config.get("apiSecret")
        self.app_id = self.config.get("appId")

    def get_provider_name(self) -> str:
        return "xfyun"

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
        if not self.app_id or not self.api_key or not self.api_secret:
            logger.error("Xfyun STT missing appId/apiKey/apiSecret")
            return ""

        ws = None
        result_segments: list[dict] = []
        cached_chunks: list[bytes] = []
        lock = Lock()
        done = Event()
        failed = Event()

        try:
            ws = create_connection(self._build_ws_url(), timeout=10, enable_multithread=True)
            ws.settimeout(1)

            def _receiver() -> None:
                while not done.is_set():
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        continue
                    except Exception as exc:
                        logger.error("Xfyun STT receive failed: %s", exc)
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
                        logger.warning("Xfyun STT non-JSON message: %s", message)
                        continue

                    code = int(payload.get("code", -1))
                    if code != 0:
                        logger.error("Xfyun STT error: code=%s message=%s", code, payload.get("message"))
                        failed.set()
                        done.set()
                        return

                    data = payload.get("data") or {}
                    result = data.get("result") or {}
                    text = self._extract_text(result)
                    with lock:
                        self._update_segments(result_segments, result, text)

                    if int(data.get("status", -1)) == 2:
                        done.set()
                        return

            Thread(target=_receiver, daemon=True).start()

            first_frame = True
            for chunk in audio_stream:
                if not chunk:
                    continue
                cached_chunks.append(chunk)
                frame = self._build_first_frame(chunk) if first_frame else self._build_continue_frame(chunk)
                ws.send(json.dumps(frame, ensure_ascii=False))
                first_frame = False

            ws.send(json.dumps(self._build_last_frame(), ensure_ascii=False))
            if not done.wait(self.RECOGNITION_TIMEOUT_SECONDS):
                logger.warning("Xfyun STT stream timeout")
        except Exception as exc:
            logger.error("Xfyun STT stream failed: %s", exc)
            failed.set()
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

        with lock:
            final_text = "".join(segment["text"] for segment in result_segments if not segment.get("deleted"))

        if not final_text and failed.is_set() and cached_chunks:
            return self._http_recognition(b"".join(cached_chunks))
        return final_text

    def _build_ws_url(self) -> str:
        if self.api_url:
            return self.api_url

        date = formatdate(timeval=time.time(), localtime=False, usegmt=True)
        signature_origin = f"host: {self.HOST}\ndate: {date}\nGET {self.PATH} HTTP/1.1"
        digest = hmac.new(self.api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode("utf-8")

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

    def _build_first_frame(self, audio_chunk: bytes) -> dict:
        return {
            "common": {"app_id": self.app_id},
            "business": {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "dwa": "wpgs",
            },
            "data": {
                "status": 0,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": base64.b64encode(audio_chunk).decode("utf-8"),
            },
        }

    @staticmethod
    def _build_continue_frame(audio_chunk: bytes) -> dict:
        return {
            "data": {
                "status": 1,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": base64.b64encode(audio_chunk).decode("utf-8"),
            }
        }

    @staticmethod
    def _build_last_frame() -> dict:
        return {
            "data": {
                "status": 2,
                "audio": "",
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
            }
        }

    @staticmethod
    def _extract_text(result: dict) -> str:
        ws_items = result.get("ws") or []
        words: list[str] = []
        for ws_item in ws_items:
            candidates = ws_item.get("cw") or []
            if candidates:
                words.append((candidates[0] or {}).get("w") or "")
        return "".join(words)

    @staticmethod
    def _update_segments(result_segments: list[dict], result: dict, text: str) -> None:
        if result.get("pgs") == "rpl":
            rg = result.get("rg") or []
            if len(rg) == 2:
                try:
                    start = max(int(rg[0]) - 1, 0)
                    end = max(int(rg[1]) - 1, start)
                    for index in range(start, min(end + 1, len(result_segments))):
                        result_segments[index]["deleted"] = True
                except (TypeError, ValueError):
                    pass

        if text:
            result_segments.append({"text": text, "deleted": False})

    def _http_recognition(self, audio_data: bytes) -> str:
        if not self.api_url:
            return ""
        try:
            headers = {
                "X-Api-Key": self.api_key or "",
                "X-Api-Secret": self.api_secret or "",
                "X-App-Id": self.app_id or "",
            }
            files = {"file": (f"audio_{uuid.uuid4().hex}.pcm", audio_data, "application/octet-stream")}
            response = httpx.post(self.api_url, headers=headers, files=files, timeout=30)
            response.raise_for_status()
            payload = response.json()
            return payload.get("text") or payload.get("result") or ""
        except Exception as exc:
            logger.error("Xfyun STT HTTP fallback failed: %s", exc)
            return ""


__all__ = ["XfyunSttService"]
