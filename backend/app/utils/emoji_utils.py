from __future__ import annotations

import re
from typing import List


_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_SPECIAL_CHARS_PATTERN = re.compile(r"[@#$%&*]")
_WHITESPACE_PATTERN = re.compile(r"\\s+")
_KAOMOJI_PATTERN = re.compile(
    r"[(][^)]{1,10}[)]|"
    r"[<][^>]{1,10}[>]|"
    r"[\\\\*][_-]{1,2}[\\\\*]|"
    r"\\\\o/|"
    r":-?[)D(]|"
    r";-?[)]|"
    r"=\\\\?[_/]"
)


def _is_emoji(char: str) -> bool:
    code = ord(char)
    return (
        0x1F600 <= code <= 0x1F64F
        or 0x1F300 <= code <= 0x1F5FF
        or 0x1F680 <= code <= 0x1F6FF
        or 0x1F900 <= code <= 0x1F9FF
        or 0x1FA70 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x26FF
        or 0x2700 <= code <= 0x27BF
    )


def is_emoji(code_point: int) -> bool:
    try:
        return _is_emoji(chr(code_point))
    except Exception:
        return False


def clean_text(text: str) -> str:
    text = text.replace("\t", "").replace("\n", "").replace("\r", "")
    text = _HTML_TAG_PATTERN.sub("", text)
    text = _SPECIAL_CHARS_PATTERN.sub("", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def contains_kaomoji(text: str) -> bool:
    if not text:
        return False
    return _KAOMOJI_PATTERN.search(text) is not None


def filter_kaomoji(text: str) -> str:
    if not text:
        return ""
    return _KAOMOJI_PATTERN.sub("", text)


def process_sentence(text: str, moods: List[str]) -> str:
    if not text:
        return ""
    text = clean_text(text)
    text = filter_kaomoji(text)
    cleaned = []
    for ch in text:
        if _is_emoji(ch):
            moods.append("happy")
            continue
        cleaned.append(ch)
    return "".join(cleaned).strip()


__all__ = ["process_sentence", "clean_text", "contains_kaomoji", "filter_kaomoji", "is_emoji"]
