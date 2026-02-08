from __future__ import annotations

import logging
from typing import Dict, Optional

from app.dialogue.tools import ToolCallback, ToolContext
from app.dialogue.memory import ConversationFactory
from app.services.role_service import SysRoleService
from app.services.device_service import SysDeviceService

logger = logging.getLogger("tool_functions")


class SessionExitFunction:
    def get_function_call_tool(self, session) -> ToolCallback:
        def _handler(params: Dict, context: ToolContext) -> str:
            chat_session = context.session
            if chat_session:
                chat_session.close_after_chat = True
            say_goodbye = params.get("sayGoodbye") or "好的，再见！期待下次聊天哦！"
            return say_goodbye

        schema = {
            "type": "object",
            "properties": {
                "sayGoodbye": {"type": "string", "description": "告别语"},
            },
            "required": ["sayGoodbye"],
        }
        return ToolCallback(
            name="func_exitSession",
            description=(
                "当用户明确表示要离开/结束对话时调用此函数。触发词汇："
                "'拜拜'、'再见'、'退下'、'走了'、'结束对话'、'退出'、"
                "'goodbye'、'bye' 等。检测到这些词汇时必须调用此函数。"
            ),
            input_schema=schema,
            handler=_handler,
            return_direct=True,
            rollback=True,
        )


class NewChatFunction:
    def get_function_call_tool(self, session) -> ToolCallback:
        def _handler(params: Dict, context: ToolContext) -> str:
            chat_session = context.session
            if chat_session and chat_session.conversation:
                chat_session.conversation.clear()
            return params.get("sayNewChat") or "让我们聊聊新的话题吧～"

        schema = {
            "type": "object",
            "properties": {
                "sayNewChat": {"type": "string", "description": "开启新对话的引导语"},
            },
            "required": ["sayNewChat"],
        }
        return ToolCallback(
            name="func_new_chat",
            description="当用户要求开启新对话时调用，清空历史并返回提示。",
            input_schema=schema,
            handler=_handler,
            return_direct=True,
        )


class ChangeRoleFunction:
    def __init__(
        self,
        role_service: SysRoleService,
        device_service: SysDeviceService,
        conversation_factory: ConversationFactory,
    ) -> None:
        self.role_service = role_service
        self.device_service = device_service
        self.conversation_factory = conversation_factory

    def get_function_call_tool(self, session) -> Optional[ToolCallback]:
        device = getattr(session, "sys_device", None) or {}
        user_id = device.get("userId")
        if not user_id:
            return None
        role_list = self.role_service.query({"userId": user_id})
        if not role_list or len(role_list) <= 1:
            return None

        role_names = [r.get("roleName") for r in role_list if r.get("roleName")]
        role_list_text = ", ".join(role_names)

        def _handler(params: Dict, context: ToolContext) -> str:
            role_name = params.get("roleName") or ""
            target = None
            for role in role_list:
                if role.get("roleName") == role_name:
                    target = role
                    break
            if not target:
                return "角色切换失败，没有对应角色。"
            try:
                device_id = device.get("deviceId")
                if device_id:
                    self.device_service.update({"deviceId": device_id, "roleId": target.get("roleId")})
                session.sys_device["roleId"] = target.get("roleId")
                session.conversation = self.conversation_factory.init_conversation(session.sys_device, target, session.session_id)
                return f"角色已切换至{role_name}"
            except Exception as exc:
                logger.error("角色切换异常: %s", exc)
                return "角色切换异常"

        schema = {
            "type": "object",
            "properties": {
                "roleName": {"type": "string", "description": f"要切换的角色名称，可选：{role_list_text}"},
            },
            "required": ["roleName"],
        }
        return ToolCallback(
            name="func_changeRole",
            description=f"当用户希望切换角色时调用。可选角色：{role_list_text}",
            input_schema=schema,
            handler=_handler,
            return_direct=True,
            rollback=True,
        )


__all__ = ["SessionExitFunction", "NewChatFunction", "ChangeRoleFunction"]
