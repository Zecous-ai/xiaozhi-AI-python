from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("tool_registry")


@dataclass
class ToolContext:
    session: Any
    extra: Dict[str, Any]


@dataclass
class ToolCallback:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any], ToolContext], Any]
    return_direct: bool = False
    rollback: bool = False

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ToolsGlobalRegistry:
    def __init__(self, global_functions: Optional[List[Any]] = None) -> None:
        self._global_functions = global_functions or []

    def get_all_functions(self, session: Any) -> Dict[str, ToolCallback]:
        temp: Dict[str, ToolCallback] = {}
        for func in self._global_functions:
            try:
                tool = func.get_function_call_tool(session)
                if tool:
                    temp[tool.name] = tool
            except Exception as exc:
                logger.error("加载全局函数失败: %s", exc)
        return temp


class ToolsSessionHolder:
    def __init__(self, session_id: str, sys_device: Dict, global_registry: ToolsGlobalRegistry) -> None:
        self.session_id = session_id
        self.sys_device = sys_device or {}
        self.global_registry = global_registry
        self._registry: Dict[str, ToolCallback] = {}

    def register_function(self, name: str, tool: ToolCallback) -> None:
        self._registry[name] = tool

    def unregister_function(self, name: str) -> bool:
        if name in self._registry:
            self._registry.pop(name, None)
            return True
        return False

    def get_function(self, name: str) -> Optional[ToolCallback]:
        return self._registry.get(name)

    def get_all_functions(self) -> List[ToolCallback]:
        return list(self._registry.values())

    def get_all_function_names(self) -> List[str]:
        return list(self._registry.keys())

    def register_global_function_tools(self, session: Any) -> None:
        function_names = self.sys_device.get("function_names") or self.sys_device.get("functionNames")
        if function_names:
            for name in str(function_names).split(","):
                name = name.strip()
                if not name:
                    continue
                tool = self.global_registry.get_all_functions(session).get(name)
                if tool:
                    self.register_function(name, tool)
            return
        # 默认由 MCP 或其他流程统一管理，不自动加载全部
        logger.debug("SessionId=%s 跳过自动注册全局函数", self.session_id)


__all__ = ["ToolCallback", "ToolContext", "ToolsGlobalRegistry", "ToolsSessionHolder"]
