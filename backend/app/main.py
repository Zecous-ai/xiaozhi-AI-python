from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.agent import router as agent_router
from app.api.config import router as config_router
from app.api.device import router as device_router
from app.api.file import router as file_router
from app.api.message import router as message_router
from app.api.role import router as role_router
from app.api.template import router as template_router
from app.api.user import router as user_router
from app.api.vl import router as vl_router
from app.communication.handler import MessageHandler
from app.communication.session import ChatSession, session_manager
from app.core.config import settings
from app.services.device_service import SysDeviceService
from app.dialogue.dialogue_service import DialogueService
from app.dialogue.intent_detector import IntentDetector
from app.dialogue.iot_service import IotService
from app.dialogue.device_mcp import DeviceMcpService
from app.dialogue.llm.chat_service import ChatService
from app.dialogue.llm.factory import ChatModelFactory
from app.dialogue.mcp_session_manager import McpSessionManager
from app.dialogue.memory import ConversationFactory, DatabaseChatMemory
from app.dialogue.message_service import MessageService
from app.dialogue.stt.factory import SttServiceFactory
from app.dialogue.token_service import TokenServiceFactory
from app.dialogue.tool_functions import ChangeRoleFunction, NewChatFunction, SessionExitFunction
from app.dialogue.tools import ToolsGlobalRegistry
from app.dialogue.tts.factory import TtsServiceFactory
from app.dialogue.vad.vad_service import VadService
from app.services.config_service import SysConfigService
from app.services.role_service import SysRoleService
from app.services.sys_message_service import SysMessageService

import uuid


logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix="/api/user")
app.include_router(device_router, prefix="/api/device")
app.include_router(role_router, prefix="/api/role")
app.include_router(message_router, prefix="/api/message")
app.include_router(template_router, prefix="/api/template")
app.include_router(config_router, prefix="/api/config")
app.include_router(agent_router, prefix="/api/agent")
app.include_router(file_router, prefix="/api/file")
app.include_router(vl_router, prefix="/api/vl")


@app.on_event("startup")
async def _startup() -> None:
    session_manager.start_background_tasks()


@app.on_event("shutdown")
async def _shutdown() -> None:
    session_manager.stop_background_tasks()


# 静态资源
web_root = Path(__file__).resolve().parents[2] / "web"
dist_dir = web_root / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")
else:
    public_dir = web_root / "public"
    if public_dir.exists():
        app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")


@app.get("/")
async def index():
    if dist_dir.exists():
        return FileResponse(dist_dir / "index.html")
    if (web_root / "index.html").exists():
        return FileResponse(web_root / "index.html")
    return {"status": "ok"}


device_service = SysDeviceService()
config_service = SysConfigService()
role_service = SysRoleService()
message_service = MessageService()
sys_message_service = SysMessageService()
token_factory = TokenServiceFactory()
stt_factory = SttServiceFactory(token_factory)
tts_factory = TtsServiceFactory(token_factory)
chat_model_factory = ChatModelFactory(config_service, role_service)
chat_memory = DatabaseChatMemory(sys_message_service)
conversation_factory = ConversationFactory(chat_memory)

tools_registry = ToolsGlobalRegistry(
    [
        SessionExitFunction(),
        NewChatFunction(),
        ChangeRoleFunction(role_service, device_service, conversation_factory),
    ]
)
mcp_session_manager = McpSessionManager(tools_registry)
chat_service = ChatService(chat_model_factory, mcp_session_manager, sys_message_service)
intent_detector = IntentDetector()
vad_service = VadService(role_service, session_manager)
vad_service.configure(settings.vad_prebuffer_ms, settings.vad_tail_keep_ms, settings.vad_audio_enhancement_enabled)
iot_service = IotService(session_manager, message_service)
device_mcp_service = DeviceMcpService(settings.mcp_max_tools_count)

dialogue_service = DialogueService(
    config_service,
    role_service,
    message_service,
    sys_message_service,
    vad_service,
    stt_factory,
    tts_factory,
    chat_service,
    intent_detector,
)
session_manager.configure(dialogue_service, device_service)
handler = MessageHandler(
    device_service,
    config_service,
    role_service,
    message_service,
    sys_message_service,
    vad_service,
    dialogue_service,
    tts_factory,
    stt_factory,
    conversation_factory,
    tools_registry,
    iot_service,
    device_mcp_service,
)


async def _handle_ws(websocket: WebSocket):
    await websocket.accept()
    # 获取设备ID
    device_id = (
        websocket.headers.get("device-id")
        or websocket.headers.get("Device-Id")
        or websocket.query_params.get("device-id")
        or websocket.query_params.get("mac_address")
        or websocket.query_params.get("uuid")
    )
    session_id = str(uuid.uuid4())
    session = ChatSession(session_id, websocket)
    await handler.after_connection(session, device_id or "")
    try:
        while True:
            data = await websocket.receive()
            if data.get("text") is not None:
                await handler.handle_text_message(session.session_id, data["text"])
            if data.get("bytes") is not None:
                await handler.handle_binary_message(session.session_id, data["bytes"])
    except WebSocketDisconnect:
        await handler.after_connection_closed(session.session_id)
    except Exception:
        await handler.after_connection_closed(session.session_id)


@app.websocket(settings.websocket_path)
async def websocket_endpoint(websocket: WebSocket):
    await _handle_ws(websocket)


@app.websocket(settings.websocket_path.rstrip("/"))
async def websocket_endpoint_no_slash(websocket: WebSocket):
    await _handle_ws(websocket)
