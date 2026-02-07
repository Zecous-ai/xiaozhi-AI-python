from __future__ import annotations

from typing import Dict, List, Optional


def _exclude(data: Dict, keys: List[str]) -> Dict:
    return {k: v for k, v in data.items() if k not in keys}


def user_to_dto(user: Optional[Dict]) -> Optional[Dict]:
    if not user:
        return None
    return _exclude(user, ["password"])


def device_to_dto(device: Optional[Dict]) -> Optional[Dict]:
    if not device:
        return None
    return device


def role_to_dto(role: Optional[Dict]) -> Optional[Dict]:
    if not role:
        return None
    return role


def permission_to_dto(permission: Dict) -> Dict:
    if not permission:
        return {}
    children = permission.get("children") or []
    permission = dict(permission)
    permission["children"] = [permission_to_dto(c) for c in children]
    return permission


def permission_list_to_dto(permissions: List[Dict]) -> List[Dict]:
    return [permission_to_dto(p) for p in permissions]


def config_to_dto(config: Optional[Dict]) -> Optional[Dict]:
    if not config:
        return None
    return _exclude(config, ["apiKey", "apiSecret", "ak", "sk"])


def agent_to_dto(agent: Optional[Dict]) -> Optional[Dict]:
    if not agent:
        return None
    return _exclude(agent, ["apiKey", "apiSecret", "ak", "sk"])


def message_to_dto(message: Optional[Dict]) -> Optional[Dict]:
    if not message:
        return None
    return message


__all__ = [
    "user_to_dto",
    "device_to_dto",
    "role_to_dto",
    "permission_list_to_dto",
    "config_to_dto",
    "agent_to_dto",
    "message_to_dto",
]
