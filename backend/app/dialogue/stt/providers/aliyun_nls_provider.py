from __future__ import annotations

import json
import logging
import uuid
from threading import Event, Lock, Thread
from urllib.parse import parse_qsl, urlencode, urlparse

from websocket import WebSocketTimeoutException, create_connection

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("aliyun_nls_stt")


class AliyunNlsSttService:
    DEFAULT_WS_URL = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
    SUCCESS_CODE = 20000000
    RECOGNITION_TIMEOUT_SECONDS = 90

    def __init__(self, config: dict, token_service) -> None:
        self.config = config or {}
        self.token_service = token_service
        self.api_url = self.config.get("apiUrl")
        self.app_key = self.config.get("apiKey")

    def get_provider_name(self) -> str:
        return "aliyun-nls"

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
        if not self.app_key:
            logger.error("Aliyun NLS missing apiKey(appKey)")
            return ""
        token = self.token_service.get_token() if self.token_service else None
        if not token:
            logger.error("Aliyun NLS failed to get token")
            return ""

        ws = None
        done = Event()
        failed = Event()
        lock = Lock()
        final_sentences: list[str] = []
        partial_text = ""
        task_id = uuid.uuid4().hex

        try:
            ws = create_connection(self._build_ws_url(token), timeout=10, enable_multithread=True)
            ws.settimeout(1)
            ws.send(json.dumps(self._build_start_command(task_id), ensure_ascii=False))

            def _receiver() -> None:
                nonlocal partial_text
                while not done.is_set():
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        continue
                    except Exception as exc:
                        logger.error("Aliyun NLS receive failed: %s", exc)
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
                        logger.warning("Aliyun NLS non-JSON message: %s", message)
                        continue

                    header = payload.get("header") or {}
                    name = header.get("name") or ""
                    status = int(header.get("status", self.SUCCESS_CODE))
                    if status != self.SUCCESS_CODE:
                        logger.error("Aliyun NLS error: name=%s status=%s payload=%s", name, status, payload)
                        failed.set()
                        done.set()
                        return

                    payload_data = payload.get("payload") or {}
                    text = payload_data.get("result") or payload_data.get("text") or ""

                    if name == "SentenceEnd" and text:
                        with lock:
                            final_sentences.append(text)
                            partial_text = ""
                    elif name == "TranscriptionResultChanged" and text:
                        with lock:
                            partial_text = text
                    elif name in ("TaskFailed", "TranscriptionFailed"):
                        failed.set()
                        done.set()
                        return
                    elif name == "TranscriptionCompleted":
                        done.set()
                        return

            Thread(target=_receiver, daemon=True).start()

            for chunk in audio_stream:
                if not chunk:
                    continue
                ws.send_binary(chunk)

            ws.send(json.dumps(self._build_stop_command(task_id), ensure_ascii=False))
            if not done.wait(self.RECOGNITION_TIMEOUT_SECONDS):
                logger.warning("Aliyun NLS stream timeout")
        except Exception as exc:
            logger.error("Aliyun NLS stream failed: %s", exc)
            failed.set()
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

        with lock:
            result = "".join(final_sentences) or partial_text
        if failed.is_set() and not result:
            return ""
        return result

    def _build_ws_url(self, token: str) -> str:
        source_url = self.api_url or self.DEFAULT_WS_URL
        parsed = urlparse(source_url)
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_params["token"] = token
        scheme = parsed.scheme
        if scheme == "https":
            scheme = "wss"
        elif scheme == "http":
            scheme = "ws"
        return parsed._replace(scheme=scheme, query=urlencode(query_params)).geturl()

    def _build_start_command(self, task_id: str) -> dict:
        return {
            "header": {
                "message_id": uuid.uuid4().hex,
                "task_id": task_id,
                "namespace": "SpeechTranscriber",
                "name": "StartTranscription",
                "appkey": self.app_key,
            },
            "payload": {
                "format": "pcm",
                "sample_rate": 16000,
                "enable_intermediate_result": True,
                "enable_punctuation_prediction": True,
                "enable_inverse_text_normalization": True,
            },
        }

    @staticmethod
    def _build_stop_command(task_id: str) -> dict:
        return {
            "header": {
                "message_id": uuid.uuid4().hex,
                "task_id": task_id,
                "namespace": "SpeechTranscriber",
                "name": "StopTranscription",
            }
        }


__all__ = ["AliyunNlsSttService"]
