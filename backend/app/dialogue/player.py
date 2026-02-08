from __future__ import annotations

import logging
from queue import PriorityQueue
from typing import Optional

from app.dialogue.sentence import Sentence
from app.utils.async_utils import schedule_coro

logger = logging.getLogger("player")


class Player:
    def __init__(self, session, message_service, session_manager) -> None:
        if session is None:
            raise ValueError("session不能为空")
        if message_service is None:
            raise ValueError("message_service不能为空")
        if session_manager is None:
            raise ValueError("session_manager不能为空")
        self.session = session
        self.message_service = message_service
        self.session_manager = session_manager
        self._queue: PriorityQueue[Sentence] = PriorityQueue()

    def append(self, sentence: Sentence) -> None:
        if sentence is None:
            return
        self._queue.put(sentence)

    def get_queue(self) -> PriorityQueue:
        return self._queue

    def send_sentence_start(self, text: Optional[str]) -> None:
        schedule_coro(self.message_service.send_tts_message(self.session, text, "sentence_start"))

    def send_opus_frame(self, frame: bytes) -> None:
        self.message_service.send_binary_message(self.session, frame)

    def send_emotion(self, emotion: Optional[str]) -> None:
        schedule_coro(self.message_service.send_emotion(self.session, emotion))

    def send_stop(self) -> None:
        if self.session.in_wakeup_response:
            self.session.in_wakeup_response = False
        schedule_coro(self.message_service.send_tts_message(self.session, None, "stop"))
        if self.session.close_after_chat:
            self.session_manager.close_session(self.session)

    def play(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break
        self.on_stop()
        logger.info("已取消音频发送任务 - SessionId: %s", self.session.session_id)

    def on_stop(self) -> None:
        return


__all__ = ["Player"]
