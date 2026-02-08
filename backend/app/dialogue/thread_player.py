from __future__ import annotations

import threading

from app.dialogue.player import Player


class ThreadPlayer(Player):
    def __init__(self, session, message_service, session_manager) -> None:
        super().__init__(session, message_service, session_manager)
        self._thread: threading.Thread | None = None

    def play(self) -> None:
        with threading.Lock():
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self.run, daemon=True)
                self._thread.start()

    def stop(self) -> None:
        super().stop()
        self._thread = None

    def run(self) -> None:
        raise NotImplementedError


__all__ = ["ThreadPlayer"]
