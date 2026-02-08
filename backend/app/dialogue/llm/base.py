from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Protocol, Tuple


class ChatModel(Protocol):
    def chat(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Tuple[str, List[Dict]]:
        ...

    def stream(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Iterable[str]:
        ...


__all__ = ["ChatModel"]
