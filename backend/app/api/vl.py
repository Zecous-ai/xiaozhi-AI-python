from __future__ import annotations

from fastapi import APIRouter, File, UploadFile, Request

from app.dialogue.llm_service import OpenAIClient
from app.services.config_service import SysConfigService
from app.communication.session import session_manager


router = APIRouter()
config_service = SysConfigService()


@router.post("/chat")
async def vl_chat(request: Request, file: UploadFile = File(...), question: str = ""):
    auth = request.headers.get("authorization", "")
    session_id = auth.replace("Bearer ", "") if auth else ""
    session = session_manager.get_session(session_id)
    if session is None:
        return "session不存在"

    config = config_service.select_model_type("vision")
    if not config:
        return "无可用的视觉模型"

    image_bytes = await file.read()
    model = config.get("configName") or "gpt-4o-mini"
    api_url = config.get("apiUrl") or "https://api.openai.com/v1"
    api_key = config.get("apiKey") or ""
    client = OpenAIClient(api_url, api_key, model)
    result = client.vision_chat(question, image_bytes, file.content_type or "image/jpeg")
    if not result:
        return "无可用的视觉模型"
    return {"success": True, "text": result}

