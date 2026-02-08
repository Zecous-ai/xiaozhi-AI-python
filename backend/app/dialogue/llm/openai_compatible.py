from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, List, Optional, Tuple

import httpx

logger = logging.getLogger("openai_compatible")


class OpenAICompatibleModel:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> None:
        self.endpoint = (endpoint or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or "gpt-3.5-turbo"
        self.temperature = temperature
        self.top_p = top_p

    def chat(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Tuple[str, List[Dict]]:
        url = f"{self.endpoint}/chat/completions"
        body: Dict[str, object] = {"model": self.model, "messages": messages}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.top_p is not None:
            body["top_p"] = self.top_p
        if tools:
            body["tools"] = tools
            if tool_choice:
                body["tool_choice"] = tool_choice
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = httpx.post(url, json=body, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return "", []
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        return content, tool_calls

    def stream(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Iterable[str]:
        url = f"{self.endpoint}/chat/completions"
        body: Dict[str, object] = {"model": self.model, "messages": messages, "stream": True}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.top_p is not None:
            body["top_p"] = self.top_p
        if tools:
            body["tools"] = tools
            if tool_choice:
                body["tool_choice"] = tool_choice
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        def _generator():
            with httpx.stream("POST", url, json=body, headers=headers, timeout=60) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    if not line.startswith("data:"):
                        continue
                    data_str = line.replace("data:", "", 1).strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        payload = json.loads(data_str)
                    except Exception:
                        continue
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content

        return _generator()


__all__ = ["OpenAICompatibleModel"]
