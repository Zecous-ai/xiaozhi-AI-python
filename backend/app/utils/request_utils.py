from __future__ import annotations

from typing import Any, Dict

from fastapi import Request


async def parse_body(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        if isinstance(data, dict):
            return data
        return {}
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return dict(form)
    return {}


__all__ = ["parse_body"]
