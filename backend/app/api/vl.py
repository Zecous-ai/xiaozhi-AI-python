from __future__ import annotations

import logging

from fastapi import APIRouter, File, Request, UploadFile

from app.communication.session import session_manager
from app.dialogue.llm_service import OpenAIClient
from app.services.config_service import SysConfigService


router = APIRouter()
config_service = SysConfigService()
logger = logging.getLogger("vl_api")


def _extract_session_id(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


@router.post("/chat")
async def vl_chat(request: Request, file: UploadFile = File(...), question: str = ""):
    no_session_message = "session不存在"
    no_vision_message = "无可用的视觉模型"

    session_id = _extract_session_id(request.headers.get("authorization"))
    session = session_manager.get_session(session_id)
    if session is None:
        return no_session_message

    config = config_service.select_model_type("vision")
    if not config:
        return no_vision_message

    image_bytes = await file.read()
    model = config.get("configName") or "gpt-4o-mini"
    api_url = config.get("apiUrl") or "https://api.openai.com/v1"
    api_key = config.get("apiKey") or ""
    if not api_key:
        return no_vision_message

    try:
        client = OpenAIClient(api_url, api_key, model)
        result = client.vision_chat(question, image_bytes, file.content_type or "image/jpeg")
    except Exception as exc:
        logger.error("Vision 调用失败: %s", exc)
        return no_vision_message

    if not result:
        return no_vision_message
    return {"success": True, "text": result}
