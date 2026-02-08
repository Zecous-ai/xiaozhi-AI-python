from __future__ import annotations

import inspect
import json
import logging
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from app.dialogue.llm.factory import ChatModelFactory
from app.dialogue.mcp_session_manager import McpSessionManager
from app.dialogue.memory import ChatMessage, ChatMemory, Conversation
from app.dialogue.tools import ToolCallback, ToolContext
from app.services.sys_message_service import SysMessageService
from app.utils.async_utils import run_coroutine_sync

logger = logging.getLogger("chat_service")


class ChatService:
    TOOL_CONTEXT_SESSION_KEY = "session"

    def __init__(
        self,
        model_factory: ChatModelFactory,
        mcp_session_manager: McpSessionManager,
        sys_message_service: SysMessageService,
    ) -> None:
        self.model_factory = model_factory
        self.mcp_session_manager = mcp_session_manager
        self.sys_message_service = sys_message_service

    def chat(self, session, message: str, use_function_call: bool) -> str:
        chat_model = self.model_factory.take_chat_model(session)
        conversation = session.conversation
        user_message = ChatMessage(role="user", content=message, metadata={})
        user_time = int(time.time() * 1000)
        if conversation:
            conversation.add(user_message, user_time)
            messages = conversation.messages()
        else:
            messages = [user_message.to_openai_dict()]

        if use_function_call:
            self.mcp_session_manager.custom_mcp_handler(session)
        tools = self._get_tools(session) if use_function_call else []
        reply, tool_calls = chat_model.chat(messages, tools=tools)
        if use_function_call and tool_calls:
            reply, rollback = self._handle_tool_calls(session, chat_model, messages, tool_calls, tools)
            self._finalize_conversation(session, conversation, reply, rollback)
            self._save_assistant_message(session, reply, "FUNCTION_CALL" if rollback else "NORMAL")
            if rollback:
                self._update_user_message_type(session, user_time, "FUNCTION_CALL")
            return reply
        self._finalize_conversation(session, conversation, reply, False)
        self._save_assistant_message(session, reply, "NORMAL")
        return reply

    def chat_stream(self, session, user_message: ChatMessage, use_function_call: bool) -> Iterable[str]:
        chat_model = self.model_factory.take_chat_model(session)
        conversation = session.conversation
        if conversation:
            conversation.add(user_message, ChatMemory.get_time_millis(user_message))
            messages = conversation.messages()
        else:
            messages = [user_message.to_openai_dict()]
        if use_function_call:
            self.mcp_session_manager.custom_mcp_handler(session)
        tools = self._get_tools(session) if use_function_call else []
        if tools:
            # 为了简化工具调用逻辑，工具场景降级为非流式
            reply, tool_calls = chat_model.chat(messages, tools=tools)
            if tool_calls:
                reply, rollback = self._handle_tool_calls(session, chat_model, messages, tool_calls, tools)
            else:
                rollback = False
            self._finalize_conversation(session, conversation, reply, rollback)
            self._save_assistant_message(session, reply, "FUNCTION_CALL" if rollback else "NORMAL")
            if rollback:
                self._update_user_message_type(session, ChatMemory.get_time_millis(user_message), "FUNCTION_CALL")
            return [reply]
        token_stream = chat_model.stream(messages, tools=None)

        def _wrapped() -> Iterable[str]:
            collected: List[str] = []
            for token in token_stream:
                collected.append(token)
                yield token
            reply = "".join(collected)
            self._finalize_conversation(session, conversation, reply, False)
            self._save_assistant_message(session, reply, "NORMAL")

        return _wrapped()

    def _get_tools(self, session) -> List[Dict]:
        tools_holder = session.tools_session_holder
        if not tools_holder or not session.support_function_call:
            return []
        tools = []
        for tool in tools_holder.get_all_functions():
            tools.append(tool.to_openai_tool())
        return tools

    def _handle_tool_calls(
        self,
        session,
        chat_model,
        messages: List[Dict],
        tool_calls: List[Dict],
        tools: List[Dict],
    ) -> Tuple[str, bool]:
        tool_map = {tool.name: tool for tool in session.tools_session_holder.get_all_functions()}
        tool_results: List[Dict] = []
        return_direct = False
        rollback = False
        tool_context = ToolContext(session=session, extra={"conversationTimestamp": session.assistant_time_millis})
        for call in tool_calls:
            func = call.get("function") or {}
            name = func.get("name")
            args_json = func.get("arguments") or "{}"
            tool = tool_map.get(name)
            if not tool:
                continue
            try:
                args = json.loads(args_json) if isinstance(args_json, str) else args_json
            except Exception:
                args = {}
            result = tool.handler(args, tool_context)
            if inspect.isawaitable(result):
                result = run_coroutine_sync(result)
            if getattr(tool, "return_direct", False):
                return_direct = True
            if getattr(tool, "rollback", False):
                rollback = True
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
                }
            )
        if return_direct and tool_results:
            return tool_results[-1]["content"], rollback
        follow_messages = list(messages)
        follow_messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
        follow_messages.extend(tool_results)
        reply, _ = chat_model.chat(follow_messages, tools=tools)
        return reply, rollback

    def _finalize_conversation(self, session, conversation, reply: str, rollback: bool) -> None:
        if not conversation:
            return
        if rollback:
            conversation.add(Conversation.ROLLBACK_MESSAGE, session.assistant_time_millis)
            return
        if reply:
            conversation.add(ChatMessage(role="assistant", content=reply, metadata={}), session.assistant_time_millis)

    def _save_assistant_message(self, session, reply: str, message_type: str) -> None:
        if not reply:
            return
        device = session.sys_device or {}
        device_id = device.get("deviceId")
        role_id = device.get("roleId")
        if not device_id or not role_id:
            return
        time_millis = session.assistant_time_millis or int(time.time() * 1000)
        create_time = self._format_time(time_millis)
        self.sys_message_service.add(
            {
                "deviceId": device_id,
                "sessionId": session.session_id,
                "sender": "assistant",
                "roleId": role_id,
                "message": reply,
                "messageType": message_type,
                "createTime": create_time,
            }
        )

    def _update_user_message_type(self, session, time_millis: int, message_type: str) -> None:
        device = session.sys_device or {}
        device_id = device.get("deviceId")
        role_id = device.get("roleId")
        if not device_id or not role_id:
            return
        create_time = self._format_time(time_millis)
        try:
            self.sys_message_service.update_message_type(device_id, int(role_id), "user", create_time, message_type)
        except Exception:
            logger.exception("更新用户消息类型失败: %s", device_id)

    @staticmethod
    def _format_time(time_millis: int) -> str:
        return datetime.fromtimestamp(time_millis / 1000.0).strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["ChatService"]
