from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.utils.exit_keyword_detector import ExitKeywordDetector

logger = logging.getLogger("intent_detector")


@dataclass
class UserIntent:
    type: str


class IntentDetector:
    def __init__(self) -> None:
        self.exit_detector = ExitKeywordDetector()

    def detect_intent(self, user_input: str) -> Optional[UserIntent]:
        if not user_input or not user_input.strip():
            return None
        if self.exit_detector.detect_exit_intent(user_input):
            logger.info("检测到退出意图: %s", user_input)
            return UserIntent(type="EXIT")
        return None


__all__ = ["IntentDetector", "UserIntent"]
