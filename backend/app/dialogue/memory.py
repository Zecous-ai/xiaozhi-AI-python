from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Protocol

from app.services.sys_message_service import SysMessageService

logger = logging.getLogger("chat_memory")


@dataclass
class ChatMessage:
    role: str
    content: Optional[str]
    metadata: Dict[str, object] = field(default_factory=dict)
    tool_calls: Optional[List[Dict]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

    def to_openai_dict(self) -> Dict:
        payload: Dict[str, object] = {"role": self.role, "content": self.content}
        if self.name:
            payload["name"] = self.name
        if self.tool_calls is not None:
            payload["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        return payload


class ChatMemory(Protocol):
    MESSAGE_TYPE_KEY = "SYS_MESSAGE_TYPE"
    TIME_MILLIS_KEY = "TIME_MILLIS"
    AUDIO_PATH = "AUDIO_PATH"

    def find(self, device_id: str, role_id: int, limit: int) -> List[ChatMessage]:
        ...

    def find_after(self, device_id: str, role_id: int, time_millis: datetime) -> List[ChatMessage]:
        ...

    def delete(self, device_id: str, role_id: int) -> None:
        ...

    @staticmethod
    def set_time_millis(message: ChatMessage, time_millis: int) -> None:
        message.metadata[ChatMemory.TIME_MILLIS_KEY] = time_millis

    @staticmethod
    def get_time_millis(message: ChatMessage) -> int:
        return int(message.metadata.get(ChatMemory.TIME_MILLIS_KEY, int(datetime.now().timestamp() * 1000)))


class DatabaseChatMemory:
    def __init__(self, sys_message_service: SysMessageService) -> None:
        self._sys_message_service = sys_message_service

    def find(self, device_id: str, role_id: int, limit: int) -> List[ChatMessage]:
        try:
            messages = list(self._sys_message_service.find(device_id, role_id, limit))
            if not messages:
                return []
            messages.sort(key=self._sort_key)
            return [self._convert_message(msg) for msg in messages if msg.get("sender") in ("user", "assistant")]
        except Exception as exc:
            logger.error("获取历史消息失败: %s", exc)
            return []

    def find_after(self, device_id: str, role_id: int, time_millis: datetime) -> List[ChatMessage]:
        try:
            messages = list(self._sys_message_service.find_after(device_id, role_id, time_millis))
            if not messages:
                return []
            messages.sort(key=self._sort_key)
            return [self._convert_message(msg) for msg in messages if msg.get("sender") in ("user", "assistant")]
        except Exception as exc:
            logger.error("获取历史消息失败: %s", exc)
            return []

    def delete(self, device_id: str, role_id: int) -> None:
        logger.warning("暂不支持删除设备历史记录: device=%s role=%s", device_id, role_id)

    @staticmethod
    def _sort_key(message: Dict) -> tuple:
        create_time = message.get("createTime")
        if isinstance(create_time, datetime):
            ts = create_time.timestamp()
        else:
            ts = DatabaseChatMemory._parse_time(create_time)
        sender = message.get("sender") or ""
        sender_order = 0 if sender == "user" else 1
        return ts, sender_order

    @staticmethod
    def _parse_time(value) -> float:
        if not value:
            return 0.0
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return datetime.fromisoformat(str(value)).timestamp()
        except Exception:
            return 0.0

    @staticmethod
    def _convert_message(message: Dict) -> ChatMessage:
        role = message.get("sender")
        content = message.get("message")
        metadata = {"messageId": message.get("messageId"), ChatMemory.MESSAGE_TYPE_KEY: message.get("messageType")}
        return ChatMessage(role=role, content=content, metadata=metadata)


class Conversation:
    ROLLBACK_MESSAGE = ChatMessage(role="system", content="__rollback__")

    def __init__(self, device: Dict, role: Dict, session_id: str) -> None:
        self.device = device
        self.role = role
        self.session_id = session_id
        self._messages: List[ChatMessage] = []

    def add(self, message: ChatMessage, time_millis: Optional[int] = None) -> None:
        if message == Conversation.ROLLBACK_MESSAGE:
            if self._messages:
                self._messages.pop()
            return
        if time_millis is not None:
            ChatMemory.set_time_millis(message, time_millis)
        self._messages.append(message)

    def clear(self) -> None:
        self._messages.clear()

    def role_system_message(self) -> Optional[ChatMessage]:
        role_desc = (self.role or {}).get("roleDesc")
        if role_desc:
            return ChatMessage(role="system", content=role_desc)
        return None

    def messages(self) -> List[Dict]:
        history = list(self._messages)
        system_msg = self.role_system_message()
        payload = []
        if system_msg:
            payload.append(system_msg.to_openai_dict())
        payload.extend([msg.to_openai_dict() for msg in history])
        return payload


class MessageWindowConversation(Conversation):
    def __init__(self, device: Dict, role: Dict, session_id: str, max_messages: int, chat_memory: ChatMemory) -> None:
        super().__init__(device, role, session_id)
        self.max_messages = max_messages
        self.chat_memory = chat_memory
        device_id = device.get("deviceId") if device else None
        role_id = role.get("roleId") if role else None
        if device_id and role_id:
            history = chat_memory.find(device_id, int(role_id), max_messages)
            self._messages.extend(history)

    def messages(self) -> List[Dict]:
        while len(self._messages) > self.max_messages + 1:
            if len(self._messages) >= 2:
                self._messages.pop(0)
                self._messages.pop(0)
            else:
                break
        return super().messages()


class ConversationFactory:
    def __init__(self, chat_memory: ChatMemory, max_messages: int = 16) -> None:
        self.chat_memory = chat_memory
        self.max_messages = max_messages

    def init_conversation(self, device: Dict, role: Dict, session_id: str) -> Conversation:
        memory_type = (role or {}).get("memoryType") or "window"
        if memory_type == "window":
            return MessageWindowConversation(device, role, session_id, self.max_messages, self.chat_memory)
        logger.warning("未知记忆类型: %s，使用 window", memory_type)
        return MessageWindowConversation(device, role, session_id, self.max_messages, self.chat_memory)


__all__ = [
    "ChatMessage",
    "ChatMemory",
    "DatabaseChatMemory",
    "Conversation",
    "MessageWindowConversation",
    "ConversationFactory",
]
