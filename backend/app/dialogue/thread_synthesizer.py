from __future__ import annotations

import threading
import time
from datetime import datetime

from app.dialogue.synthesizer import Synthesizer


class ThreadSynthesizer(Synthesizer):
    def __init__(self, session, player) -> None:
        super().__init__(session, player)
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        super().cancel()

    def run(self) -> None:
        while True:
            if self.is_aborted():
                break
            sentence = self.pop_sentence()
            if sentence is None:
                if self._is_last:
                    break
                time.sleep(0.06)
                continue
            if sentence.begin_synthesis is None:
                sentence.begin_synthesis = datetime.utcnow()
            self.do_synthesize(sentence)

    def do_synthesize(self, sentence) -> None:
        raise NotImplementedError


__all__ = ["ThreadSynthesizer"]
