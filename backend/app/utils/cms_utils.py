from __future__ import annotations

import socket
from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def _server_ip() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            return "127.0.0.1"
        return ip
    except Exception:
        return "127.0.0.1"


def get_server_address() -> str:
    domain = getattr(settings, "server_domain", "")
    if domain:
        return f"https://{domain}"
    ip = _server_ip()
    return f"http://{ip}:{settings.server_port}"


def get_websocket_address() -> str:
    domain = getattr(settings, "server_domain", "")
    if domain:
        return f"wss://ws.{domain}{settings.websocket_path}"
    ip = _server_ip()
    return f"ws://{ip}:{settings.server_port}{settings.websocket_path}"


def get_ota_address() -> str:
    domain = getattr(settings, "server_domain", "")
    if domain:
        return f"https://{domain}/api/device/ota"
    ip = _server_ip()
    return f"http://{ip}:{settings.server_port}/api/device/ota"


__all__ = ["get_server_address", "get_websocket_address", "get_ota_address"]
