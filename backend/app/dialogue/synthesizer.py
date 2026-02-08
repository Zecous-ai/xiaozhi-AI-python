from __future__ import annotations

import logging
import threading
from typing import Iterable, List, Optional

from app.dialogue.dialogue_helper import DialogueHelper
from app.dialogue.sentence import Sentence

logger = logging.getLogger("synthesizer")


class Synthesizer:
    def __init__(self, session, player) -> None:
        self.session = session
        self.player = player
        self._sentences: List[Sentence] = []
        self._lock = threading.Lock()
        self._aborted = False
        self._is_last = False
        self._token_thread: Optional[threading.Thread] = None

    def cancel(self) -> None:
        self._aborted = True

    def is_aborted(self) -> bool:
        return self._aborted

    def is_dialog(self) -> bool:
        return (not self._is_last) or bool(self._sentences)

    def set_last(self) -> None:
        self._is_last = True

    def append_sentence(self, text: str) -> None:
        if not text:
            return
        sentence = Sentence(text=text)
        sentence.assistant_time_millis = self.session.assistant_time_millis
        with self._lock:
            self._sentences.append(sentence)

    def pop_sentence(self) -> Optional[Sentence]:
        with self._lock:
            if not self._sentences:
                return None
            return self._sentences.pop(0)

    def clear_all_sentences(self) -> None:
        with self._lock:
            self._sentences.clear()

    def start_synthesis(self, token_stream: Iterable[str]) -> None:
        helper = DialogueHelper()

        def _consume() -> None:
            try:
                for sentence in helper.process(token_stream):
                    if self._aborted:
                        break
                    self.append_sentence(sentence)
            except Exception as exc:
                if not self._aborted:
                    logger.error("流式响应出错: %s", exc)
                    self.append_sentence("抱歉，我在处理您的请求时遇到问题。")
            finally:
                if not self._aborted:
                    self.set_last()

        self._token_thread = threading.Thread(target=_consume, daemon=True)
        self._token_thread.start()


__all__ = ["Synthesizer"]
