from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import threading
import time
import uuid
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx
import jwt

logger = logging.getLogger("token_service")

COZE_API_ENDPOINT = "api.coze.cn"
COZE_TOKEN_URL = "https://api.coze.cn/api/permission/oauth2/token"
COZE_DEFAULT_DURATION = 86399

ALIYUN_REGION_ID = "cn-shanghai"
ALIYUN_DOMAIN = "nls-meta.cn-shanghai.aliyuncs.com"
ALIYUN_API_VERSION = "2019-02-28"
ALIYUN_ACTION = "CreateToken"


@dataclass
class TokenCache:
    token: str
    expire_time: datetime
    last_used_time: datetime
    create_time: datetime

    def update_last_used(self) -> None:
        self.last_used_time = datetime.now(timezone.utc)

    def needs_refresh(self) -> bool:
        return datetime.now(timezone.utc) + timedelta(hours=1) >= self.expire_time

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expire_time

    def needs_cache_cleanup(self) -> bool:
        return datetime.now(timezone.utc) - self.last_used_time > timedelta(hours=24)


class TokenService:
    def get_provider_name(self) -> str:
        raise NotImplementedError

    def get_token(self) -> str:
        raise NotImplementedError

    def clear_token_cache(self) -> None:
        raise NotImplementedError


class AliyunTokenService(TokenService):
    def __init__(self, config: dict) -> None:
        self.ak = config.get("ak")
        self.sk = config.get("sk")
        self.config_id = config.get("configId")
        self._cache: Optional[TokenCache] = None
        self._lock = threading.Lock()

    def get_provider_name(self) -> str:
        return "aliyun"

    def clear_token_cache(self) -> None:
        self._cache = None

    def get_token(self) -> str:
        if self._cache and not self._cache.needs_refresh() and not self._cache.is_expired():
            self._cache.update_last_used()
            return self._cache.token
        return self._refresh_token()

    def _refresh_token(self) -> str:
        if not self.ak or not self.sk:
            raise RuntimeError("Aliyun Token 缺少 AK/SK 配置")
        with self._lock:
            if self._cache and not self._cache.needs_refresh() and not self._cache.is_expired():
                self._cache.update_last_used()
                return self._cache.token

            params = {
                "Action": ALIYUN_ACTION,
                "Version": ALIYUN_API_VERSION,
                "Format": "JSON",
                "RegionId": ALIYUN_REGION_ID,
                "AccessKeyId": self.ak,
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": str(uuid.uuid4()),
                "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            params["Signature"] = self._sign(params, self.sk)
            url = f"https://{ALIYUN_DOMAIN}/"
            resp = httpx.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                raise RuntimeError(f"Aliyun Token 请求失败: {resp.status_code} {resp.text}")
            data = resp.json()
            token_info = data.get("Token") or {}
            token = token_info.get("Id")
            expire_time = token_info.get("ExpireTime")
            if not token or not expire_time:
                raise RuntimeError(f"Aliyun Token 响应异常: {data}")
            expire_dt = datetime.fromtimestamp(int(expire_time), tz=timezone.utc)
            now = datetime.now(timezone.utc)
            self._cache = TokenCache(token=token, expire_time=expire_dt, last_used_time=now, create_time=now)
            return token

    @staticmethod
    def _sign(params: Dict[str, str], secret: str) -> str:
        def _percent_encode(value: str) -> str:
            return urllib.parse.quote(str(value), safe="~")

        sorted_params = sorted(params.items(), key=lambda item: item[0])
        canonicalized = "&".join(f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted_params)
        string_to_sign = f"GET&%2F&{_percent_encode(canonicalized)}"
        key = f"{secret}&".encode("utf-8")
        signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(signature).decode("utf-8")


class CozeTokenService(TokenService):
    def __init__(self, config: dict) -> None:
        self.oauth_app_id = config.get("appId")
        self.public_key = config.get("ak")
        self.private_key = config.get("sk")
        self._cache: Optional[TokenCache] = None
        self._lock = threading.Lock()

    def get_provider_name(self) -> str:
        return "coze"

    def clear_token_cache(self) -> None:
        self._cache = None

    def get_token(self) -> str:
        if self._cache and not self._cache.needs_refresh() and not self._cache.is_expired():
            self._cache.update_last_used()
            return self._cache.token
        return self._refresh_token()

    def _refresh_token(self) -> str:
        with self._lock:
            if self._cache and not self._cache.needs_refresh() and not self._cache.is_expired():
                self._cache.update_last_used()
                return self._cache.token
            jwt_token = self._generate_jwt()
            access_token = self._request_access_token(jwt_token)
            expire = datetime.now(timezone.utc) + timedelta(seconds=COZE_DEFAULT_DURATION)
            now = datetime.now(timezone.utc)
            self._cache = TokenCache(access_token, expire, now, now)
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


class TokenServiceFactory:
    def __init__(self) -> None:
        self._cache: Dict[str, TokenService] = {}
        self._lock = threading.Lock()

    def _cache_key(self, provider: str, config_id: int | None) -> str:
        return f"{provider}:{config_id or -1}"

    def get_token_service(self, config: dict) -> TokenService:
        provider = (config.get("provider") or "").lower()
        key = self._cache_key(provider, config.get("configId"))
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            service = self._create_service(provider, config)
            self._cache[key] = service
            return service

    def _create_service(self, provider: str, config: dict) -> TokenService:
        if provider in ("aliyun", "aliyun-nls", "aliyun_nls"):
            return AliyunTokenService(config)
        if provider == "coze":
            return CozeTokenService(config)
        raise ValueError(f"不支持的 Token 提供商: {provider}")

    def remove_cache(self, config: dict) -> None:
        provider = (config.get("provider") or "").lower()
        key = self._cache_key(provider, config.get("configId"))
        service = self._cache.pop(key, None)
        if service:
            service.clear_token_cache()

    def cleanup_unused_tokens(self) -> None:
        with self._lock:
            keys_to_remove = []
            for key, service in self._cache.items():
                if isinstance(service, AliyunTokenService):
                    cache = service._cache
                    if cache and cache.needs_cache_cleanup():
                        service.clear_token_cache()
                        keys_to_remove.append(key)
            for key in keys_to_remove:
                self._cache.pop(key, None)


__all__ = [
    "TokenCache",
    "TokenService",
    "AliyunTokenService",
    "CozeTokenService",
    "TokenServiceFactory",
]
