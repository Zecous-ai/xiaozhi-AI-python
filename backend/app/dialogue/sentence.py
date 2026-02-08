from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.utils.emoji_utils import process_sentence

logger = logging.getLogger("sentence")

_counter_lock = threading.Lock()
_counter = 0


def _next_seq() -> int:
    global _counter
    with _counter_lock:
        _counter += 1
        return _counter


@dataclass(order=True)
class Sentence:
    sort_index: int = field(init=False, repr=False)
    text: str
    audio_path: Optional[Path] = None
    should_merge: bool = True
    assistant_time_millis: Optional[int] = None
    retry_count: int = 0
    is_retry: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    begin_synthesis: datetime = field(default_factory=datetime.utcnow)
    end_synthesis: datetime = field(default_factory=datetime.utcnow)
    moods: List[str] = field(default_factory=list)
    text_for_speech: Optional[str] = None

    def __post_init__(self) -> None:
        seq = _next_seq()
        self.sort_index = seq

    @property
    def seq(self) -> int:
        return self.sort_index

    def set_audio(self, path: Path) -> None:
        if path.exists():
            self.audio_path = path
        else:
            logger.error("音频文件不存在: %s", path)

    def get_synthesis_duration_ms(self) -> int:
        return int((self.end_synthesis - self.begin_synthesis).total_seconds() * 1000)

    def get_moods(self) -> List[str]:
        if not self.moods:
            moods: List[str] = []
            self.text_for_speech = process_sentence(self.text, moods)
            self.moods.extend(moods)
        return self.moods

    def get_text_for_speech(self) -> str:
        if self.text_for_speech is None:
            moods: List[str] = []
            self.text_for_speech = process_sentence(self.text, moods)
            self.moods.extend(moods)
        return self.text_for_speech or ""

    def is_only_emoji(self) -> bool:
        return bool(self.moods) and len(self.text.strip()) <= 4


__all__ = ["Sentence"]
