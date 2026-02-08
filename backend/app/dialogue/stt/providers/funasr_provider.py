from __future__ import annotations

import json
import logging
from threading import Event, Lock, Thread

from websocket import WebSocketTimeoutException, create_connection

from app.dialogue.stt.base import AudioStream, SttService

logger = logging.getLogger("funasr_stt")


class FunASRSttService:
    RECOGNITION_TIMEOUT_SECONDS = 90
    SPEAKING_START = {
        "mode": "online",
        "wav_name": "voice.wav",
        "is_speaking": True,
        "wav_format": "pcm",
        "chunk_size": [5, 10, 5],
        "itn": True,
    }
    SPEAKING_END = {"is_speaking": False}

    def __init__(self, config: dict) -> None:
        self.config = config or {}
        self.api_url = self.config.get("apiUrl")

    def get_provider_name(self) -> str:
        return "funasr"

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
        if not self.api_url:
            logger.error("FunASR missing apiUrl")
            return ""

        ws = None
        done = Event()
        failed = Event()
        lock = Lock()
        final_text = ""
        partial_text = ""

        try:
            ws = create_connection(self.api_url, timeout=10, enable_multithread=True)
            ws.settimeout(1)
            ws.send(json.dumps(self.SPEAKING_START, ensure_ascii=False))

            def _receiver() -> None:
                nonlocal final_text, partial_text
                while not done.is_set():
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        continue
                    except Exception as exc:
                        logger.error("FunASR receive failed: %s", exc)
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
                        logger.warning("FunASR non-JSON message: %s", message)
                        continue

                    text = payload.get("text") or payload.get("result") or ""
                    if text:
                        with lock:
                            partial_text = text

                    is_final = payload.get("is_final")
                    if str(is_final).lower() in ("true", "1"):
                        with lock:
                            final_text = text or partial_text
                        done.set()
                        return

            Thread(target=_receiver, daemon=True).start()

            for chunk in audio_stream:
                if not chunk:
                    continue
                ws.send_binary(chunk)

            ws.send(json.dumps(self.SPEAKING_END, ensure_ascii=False))
            if not done.wait(self.RECOGNITION_TIMEOUT_SECONDS):
                logger.warning("FunASR stream timeout")
        except Exception as exc:
            logger.error("FunASR stream failed: %s", exc)
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


__all__ = ["FunASRSttService"]
