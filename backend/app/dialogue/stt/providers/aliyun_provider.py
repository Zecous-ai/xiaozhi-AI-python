from __future__ import annotations

import logging
from threading import Event, Lock

import httpx

from app.dialogue.stt.base import AudioStream, SttService
from app.utils.audio_constants import SAMPLE_RATE

logger = logging.getLogger("aliyun_stt")


class AliyunSttService:
    RECOGNITION_TIMEOUT_SECONDS = 90

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
        stream = AudioStream()
        stream.put(audio_data)
        stream.close()
        return self.stream_recognition(stream)

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        if not self.api_key:
            logger.error("Aliyun STT missing apiKey")
            return ""

        model_name = self._resolve_model_name()
        callback = _AliyunRecognitionCallback()
        cached_chunks: list[bytes] = []

        try:
            import dashscope  # type: ignore
            from dashscope.audio.asr import Recognition  # type: ignore

            dashscope.api_key = self.api_key
            recognizer = Recognition(
                model=model_name,
                callback=callback,
                format="pcm",
                sample_rate=SAMPLE_RATE,
            )
            recognizer.start()
            try:
                for chunk in audio_stream:
                    if not chunk:
                        continue
                    cached_chunks.append(chunk)
                    recognizer.send_audio_frame(chunk)
            finally:
                recognizer.stop()

            if not callback.done_event.wait(self.RECOGNITION_TIMEOUT_SECONDS):
                logger.warning("Aliyun STT stream timeout")

            result = callback.get_text()
            if result:
                return result
        except Exception as exc:
            logger.error("Aliyun STT stream failed: %s", exc)

        if cached_chunks:
            return self._http_recognition(b"".join(cached_chunks))
        return ""

    def _resolve_model_name(self) -> str:
        model_name = (self.model or "").lower()
        if "gummy" in model_name:
            return self.model
        if "qwen" in model_name:
            return self.model
        if "paraformer" in model_name or "fun-asr" in model_name:
            return self.model
        if self.model:
            logger.info("Aliyun STT model %s is not recognized, fallback to paraformer-realtime-v2", self.model)
        return "paraformer-realtime-v2"

    def _http_recognition(self, audio_data: bytes) -> str:
        if not self.api_url:
            logger.error("Aliyun STT missing apiUrl")
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
            logger.error("Aliyun STT HTTP fallback failed: %s", exc)
            return ""


class _AliyunRecognitionCallback:
    def __init__(self) -> None:
        self.sentences: list[str] = []
        self.partial_text = ""
        self.done_event = Event()
        self._lock = Lock()

    def on_open(self) -> None:
        return

    def on_complete(self) -> None:
        self.done_event.set()

    def on_error(self, result) -> None:
        logger.error("Aliyun STT callback error: %s", result)
        self.done_event.set()

    def on_close(self) -> None:
        return

    def on_event(self, result) -> None:
        try:
            from dashscope.audio.asr import RecognitionResult  # type: ignore
        except Exception:
            return

        sentence = result.get_sentence() if hasattr(result, "get_sentence") else None
        if isinstance(sentence, list):
            for item in sentence:
                self._consume_sentence(item, RecognitionResult)
        elif isinstance(sentence, dict):
            self._consume_sentence(sentence, RecognitionResult)

    def _consume_sentence(self, sentence: dict, recognition_result_cls) -> None:
        text = sentence.get("text") or ""
        if not text:
            return
        with self._lock:
            if recognition_result_cls.is_sentence_end(sentence):
                self.sentences.append(text)
                self.partial_text = ""
            else:
                self.partial_text = text

    def get_text(self) -> str:
        with self._lock:
            return "".join(self.sentences) or self.partial_text


__all__ = ["AliyunSttService"]
