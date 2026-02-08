from __future__ import annotations

import re
from typing import Iterable, List

from app.utils.emoji_utils import contains_kaomoji, filter_kaomoji, is_emoji


class DialogueHelper:
    SENTENCE_END_PATTERN = re.compile(r"[。！？!?]")
    PAUSE_PATTERN = re.compile(r"[，、；,;]")
    NEWLINE_PATTERN = re.compile(r"[\n\r]")
    NUMBER_PATTERN = re.compile(r"\d+\.\d+")
    MIN_SENTENCE_LENGTH = 5

    def __init__(self) -> None:
        self.current_sentence: List[str] = []
        self.context_buffer: List[str] = []

    def on_token(self, token: str) -> List[str]:
        sentences: List[str] = []
        if not token:
            return sentences
        i = 0
        while i < len(token):
            ch = token[i]
            code_point = ord(ch)
            self.context_buffer.append(ch)
            if len(self.context_buffer) > 20:
                self.context_buffer = self.context_buffer[-20:]
            self.current_sentence.append(ch)

            is_end = bool(self.SENTENCE_END_PATTERN.search(ch))
            is_pause = bool(self.PAUSE_PATTERN.search(ch))
            is_newline = bool(self.NEWLINE_PATTERN.search(ch))
            is_emoji_char = is_emoji(code_point)
            contains_kao = contains_kaomoji("".join(self.current_sentence)) if len(self.current_sentence) >= 3 else False

            if ch == "." and is_end:
                context = "".join(self.context_buffer)
                if self.NUMBER_PATTERN.search(context):
                    is_end = False

            should_send = False
            if is_end or is_newline:
                should_send = True
            elif (is_pause or is_emoji_char or contains_kao) and len(self.current_sentence) >= self.MIN_SENTENCE_LENGTH:
                should_send = True

            if should_send and len(self.current_sentence) >= self.MIN_SENTENCE_LENGTH:
                sentence = "".join(self.current_sentence).strip()
                sentence = filter_kaomoji(sentence)
                if self._contains_substantial_content(sentence):
                    sentences.append(sentence)
                    self.current_sentence = []

            i += 1
        return sentences

    def on_complete(self) -> List[str]:
        sentence = "".join(self.current_sentence).strip()
        if sentence:
            return [sentence]
        return []

    def process(self, token_stream: Iterable[str]) -> Iterable[str]:
        for token in token_stream:
            for sentence in self.on_token(token):
                yield sentence
        for sentence in self.on_complete():
            yield sentence

    def _contains_substantial_content(self, text: str) -> bool:
        if not text or len(text.strip()) < self.MIN_SENTENCE_LENGTH:
            return False
        stripped = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
        return len(stripped) >= 2


__all__ = ["DialogueHelper"]
