from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class MessageBase(BaseModel):
    type: str = "unknown"

    model_config = ConfigDict(extra="allow")


class HelloFeatures(BaseModel):
    mcp: Optional[bool] = False
    aec: Optional[bool] = False


class AudioParams(BaseModel):
    channels: int
    format: str
    sample_rate: int = Field(alias="sample_rate")
    frame_duration: int = Field(alias="frame_duration")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def opus(cls) -> "AudioParams":
        return cls(channels=1, format="opus", sample_rate=16000, frame_duration=60)


class HelloMessage(MessageBase):
    type: str = "hello"
    features: Optional[HelloFeatures] = None
    audio_params: Optional[AudioParams] = Field(default=None, alias="audio_params")

    model_config = ConfigDict(populate_by_name=True)


class HelloMessageResp(BaseModel):
    type: str = "hello"
    transport: str
    session_id: str = Field(alias="session_id")
    audio_params: AudioParams = Field(alias="audio_params")

    model_config = ConfigDict(populate_by_name=True)


class ListenMessage(MessageBase):
    type: str = "listen"
    state: Optional[str] = None
    mode: Optional[str] = None
    text: Optional[str] = None


class IotMessage(MessageBase):
    type: str = "iot"
    update: Optional[bool] = None
    session_id: Optional[str] = Field(default=None, alias="session_id")
    states: Optional[List[Dict[str, Any]]] = None
    descriptors: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(populate_by_name=True)


class AbortMessage(MessageBase):
    type: str = "abort"
    reason: Optional[str] = None


class GoodbyeMessage(MessageBase):
    type: str = "goodbye"


class DeviceMcpMessage(MessageBase):
    type: str = "mcp"
    session_id: Optional[str] = Field(default=None, alias="session_id")
    payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True)


class UnknownMessage(MessageBase):
    type: str = "unknown"


def parse_message(data: Dict[str, Any]) -> MessageBase:
    msg_type = data.get("type")
    if msg_type == "hello":
        return HelloMessage.model_validate(data)
    if msg_type == "listen":
        return ListenMessage.model_validate(data)
    if msg_type == "iot":
        return IotMessage.model_validate(data)
    if msg_type == "abort":
        return AbortMessage.model_validate(data)
    if msg_type == "goodbye":
        return GoodbyeMessage.model_validate(data)
    if msg_type == "mcp":
        return DeviceMcpMessage.model_validate(data)
    return UnknownMessage.model_validate(data)


__all__ = [
    "MessageBase",
    "HelloMessage",
    "HelloMessageResp",
    "HelloFeatures",
    "AudioParams",
    "ListenMessage",
    "IotMessage",
    "AbortMessage",
    "GoodbyeMessage",
    "DeviceMcpMessage",
    "UnknownMessage",
    "parse_message",
]
