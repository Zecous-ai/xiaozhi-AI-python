from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx
import jwt


logger = logging.getLogger("token_service")

COZE_API_ENDPOINT = "api.coze.cn"
COZE_TOKEN_URL = "https://api.coze.cn/api/permission/oauth2/token"
COZE_DEFAULT_DURATION = 86399


@dataclass
class TokenCache:
    token: str
    expire_time: datetime

    def needs_refresh(self) -> bool:
        return datetime.utcnow() + timedelta(minutes=5) >= self.expire_time


class CozeTokenService:
    def __init__(self, config: dict) -> None:
        self.oauth_app_id = config.get("appId")
        self.public_key = config.get("ak")
        self.private_key = config.get("sk")
        self._cache: Optional[TokenCache] = None

    def get_token(self) -> str:
        if self._cache and not self._cache.needs_refresh():
            return self._cache.token
        token = self._refresh_token()
        return token

    def _refresh_token(self) -> str:
        jwt_token = self._generate_jwt()
        access_token = self._request_access_token(jwt_token)
        expire = datetime.utcnow() + timedelta(seconds=COZE_DEFAULT_DURATION)
        self._cache = TokenCache(access_token, expire)
        return access_token

    def _generate_jwt(self) -> str:
        now = int(time.time())
        headers = {"alg": "RS256", "typ": "JWT", "kid": self.public_key}
        payload = {
            "iss": self.oauth_app_id,
            "aud": COZE_API_ENDPOINT,
            "iat": now,
            "exp": now + 600,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers=headers)

    def _request_access_token(self, jwt_token: str) -> str:
        headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
        body = {"duration_seconds": COZE_DEFAULT_DURATION, "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer"}
        response = httpx.post(COZE_TOKEN_URL, json=body, headers=headers, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Coze Token 请求失败: {response.status_code} {response.text}")
        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError("Coze Token 响应缺少 access_token")
        return access_token


__all__ = ["CozeTokenService"]
