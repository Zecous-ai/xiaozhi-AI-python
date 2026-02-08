from __future__ import annotations

import queue
from typing import Iterable, Optional, Protocol


class AudioStream:
    def __init__(self) -> None:
        self._queue: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._closed = False

    def put(self, data: bytes) -> None:
        if not self._closed:
            self._queue.put(data)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._queue.put(None)

    def __iter__(self) -> Iterable[bytes]:
        while True:
            item = self._queue.get()
            if item is None:
                break
            yield item


class SttService(Protocol):
    def get_provider_name(self) -> str:
        ...

    def recognition(self, audio_data: bytes) -> str:
        ...

    def stream_recognition(self, audio_stream: AudioStream) -> str:
        ...

    def supports_streaming(self) -> bool:
        return False


__all__ = ["AudioStream", "SttService"]
