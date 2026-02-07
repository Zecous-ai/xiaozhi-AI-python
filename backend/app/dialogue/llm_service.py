from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx


logger = logging.getLogger("llm_service")


class OpenAIClient:
    def __init__(self, endpoint: str, api_key: str, model: str) -> None:
        self.endpoint = endpoint.rstrip("/") if endpoint else "https://api.openai.com/v1"
        self.api_key = api_key
        self.model = model

    def chat(self, system_prompt: str, user_message: str) -> Optional[str]:
        url = f"{self.endpoint}/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            return message.get("content")
        except Exception as exc:
            logger.error("OpenAI chat 失败: %s", exc)
            return None

    def vision_chat(self, question: str, image_bytes: bytes, image_mime: str) -> Optional[str]:
        url = f"{self.endpoint}/chat/completions"
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:{image_mime};base64,{image_b64}"
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            return message.get("content")
        except Exception as exc:
            logger.error("OpenAI vision 失败: %s", exc)
            return None


__all__ = ["OpenAIClient"]
