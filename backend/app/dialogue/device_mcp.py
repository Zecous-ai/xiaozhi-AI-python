from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.dialogue.tools import ToolCallback, ToolContext
from app.utils.async_utils import run_coroutine_sync

logger = logging.getLogger("device_mcp")


@dataclass
class DeviceMcpHolder:
    mcp_initialized: bool = False
    mcp_cursor: Optional[str] = ""
    _request_id: int = 10000
    pending_requests: Dict[int, asyncio.Future] = field(default_factory=dict)

    def next_request_id(self) -> int:
        current = self._request_id
        self._request_id += 1
        return current


class DeviceMcpService:
    def __init__(self, max_tools_count: int = 32) -> None:
        self.max_tools_count = max_tools_count

    async def initialize(self, session) -> None:
        result = await self._send_initialize(session)
        if result:
            session.device_mcp_holder.mcp_initialized = True
            await self._send_tools_list(session)

    async def _send_initialize(self, session) -> Optional[Dict]:
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": session.device_mcp_holder.next_request_id(),
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "xiaozhi-mqtt-client", "version": "1.0.0"},
                "capabilities": {"vision": {"url": self._vision_url(), "token": session.session_id}},
            },
        }
        message = {"type": "mcp", "session_id": session.session_id, "payload": payload}
        return await self.send_mcp_request(session, message)

    async def _send_tools_list(self, session) -> None:
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": session.device_mcp_holder.next_request_id(),
            "params": {"cursor": session.device_mcp_holder.mcp_cursor or ""},
        }
        message = {"type": "mcp", "session_id": session.session_id, "payload": payload}
        result = await self.send_mcp_request(session, message)
        if not result:
            return
        payload_result = (result.get("payload") or {}).get("result") or {}
        tools = payload_result.get("tools") or []
        next_cursor = payload_result.get("nextCursor")
        if not tools:
            return
        current_count = len(session.tools_session_holder.get_all_functions())
        if current_count + len(tools) > self.max_tools_count:
            return
        for tool in tools:
            self._register_mcp_tool(session, tool)
        if next_cursor:
            session.device_mcp_holder.mcp_cursor = str(next_cursor)
            await self._send_tools_list(session)
        else:
            session.device_mcp_holder.mcp_cursor = None

    def _register_mcp_tool(self, session, tool: Dict[str, Any]) -> None:
        name = tool.get("name") or ""
        description = tool.get("description") or ""
        input_schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
        func_name = f"mcp_{name.replace('.', '_')}"

        async def _call(params: Dict[str, Any], context: ToolContext) -> Any:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": session.device_mcp_holder.next_request_id(),
                "params": {"name": name, "arguments": params},
            }
            message = {"type": "mcp", "session_id": session.session_id, "payload": payload}
            response = await self.send_mcp_request(session, message)
            if not response:
                return "操作失败"
            result = (response.get("payload") or {}).get("result")
            if result and str(result.get("isError")) == "false":
                return result.get("content")
            error = (response.get("payload") or {}).get("error")
            if error:
                return error.get("message") or error
            return "操作失败"

        def _handler(params: Dict[str, Any], context: ToolContext) -> Any:
            return run_coroutine_sync(_call(params, context))

        tool_callback = ToolCallback(
            name=func_name,
            description=description,
            input_schema=input_schema if isinstance(input_schema, dict) else {"type": "object"},
            handler=_handler,
            return_direct=False,
        )
        session.tools_session_holder.register_function(func_name, tool_callback)

    async def send_mcp_request(self, session, message: Dict[str, Any]) -> Optional[Dict]:
        payload = message.get("payload") or {}
        request_id = payload.get("id")
        if request_id is None:
            return None
        future = asyncio.get_running_loop().create_future()
        session.device_mcp_holder.pending_requests[int(request_id)] = future
        await session.send_text_message(json.dumps(message, ensure_ascii=False))
        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except Exception as exc:
            logger.error("MCP 请求超时: %s", exc)
            session.device_mcp_holder.pending_requests.pop(int(request_id), None)
            return None

    def handle_mcp_response(self, session, message: Dict[str, Any]) -> None:
        payload = message.get("payload") or {}
        request_id = payload.get("id")
        if request_id is None:
            return
        future = session.device_mcp_holder.pending_requests.pop(int(request_id), None)
        if future and not future.done():
            future.set_result(message)

    @staticmethod
    def _vision_url() -> str:
        if settings.server_domain:
            return f"http://{settings.server_domain}/api/vl/chat"
        port = settings.server_port
        return f"http://127.0.0.1:{port}/api/vl/chat"


__all__ = ["DeviceMcpHolder", "DeviceMcpService"]
