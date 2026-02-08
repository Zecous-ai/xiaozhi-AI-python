from __future__ import annotations

from typing import Any

from app.dialogue.tools import ToolsGlobalRegistry


class McpSessionManager:
    def __init__(self, tools_registry: ToolsGlobalRegistry) -> None:
        self._tools_registry = tools_registry

    def custom_mcp_handler(self, session: Any) -> None:
        tools_holder = getattr(session, "tools_session_holder", None)
        if not tools_holder:
            return
        global_functions = self._tools_registry.get_all_functions(session)
        for name, tool in global_functions.items():
            tools_holder.register_function(name, tool)


__all__ = ["McpSessionManager"]
