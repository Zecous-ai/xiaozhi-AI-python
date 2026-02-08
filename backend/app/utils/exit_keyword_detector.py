from __future__ import annotations

import re
from typing import List


class ExitKeywordDetector:
    EXIT_KEYWORDS: List[str] = [
        "拜拜",
        "再见",
        "退下",
        "走了",
        "我走了",
        "我要走了",
        "结束对话",
        "退出",
        "下线",
        "结束",
        "告辞",
        "告退",
        "离开",
        "goodbye",
        "bye",
        "bye bye",
        "byebye",
        "see you",
        "see ya",
    ]

    EXACT_PATTERNS = [
        re.compile(r".*拜拜.*", re.IGNORECASE),
        re.compile(r".*再见.*", re.IGNORECASE),
        re.compile(r".*退下.*", re.IGNORECASE),
        re.compile(r".*走了.*", re.IGNORECASE),
        re.compile(r".*我?要?走了.*", re.IGNORECASE),
        re.compile(r".*结束对话.*", re.IGNORECASE),
        re.compile(r".*退出.*", re.IGNORECASE),
        re.compile(r".*告辞.*", re.IGNORECASE),
        re.compile(r".*告退.*", re.IGNORECASE),
        re.compile(r".*(?:我|你)?(?:先)?(?:要)?离开.*", re.IGNORECASE),
        re.compile(r".*(?:我|你)?(?:先)?下线.*", re.IGNORECASE),
        re.compile(r".*bye\s*bye.*", re.IGNORECASE),
        re.compile(r".*goodbye.*", re.IGNORECASE),
        re.compile(r".*see\s+you.*", re.IGNORECASE),
        re.compile(r".*see\s+ya.*", re.IGNORECASE),
    ]

    EXCLUDE_PATTERNS = [
        re.compile(r".*不.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*别.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*不要.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*为什么.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*怎么.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*如何.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*能否.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*可以.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*会.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*什么.*(?:退出|离开|走|退下|结束).*", re.IGNORECASE),
        re.compile(r".*don't.*(?:leave|exit|quit|bye).*", re.IGNORECASE),
        re.compile(r".*not.*(?:leave|exit|quit|bye).*", re.IGNORECASE),
    ]

    def detect_exit_intent(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        normalized = text.strip().lower()

        for pattern in self.EXCLUDE_PATTERNS:
            if pattern.match(normalized):
                return False

        for pattern in self.EXACT_PATTERNS:
            if pattern.match(normalized):
                return True

        if len(normalized) <= 15:
            for keyword in self.EXIT_KEYWORDS:
                if keyword.lower() in normalized:
                    return True
        return False


__all__ = ["ExitKeywordDetector"]
