from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from app.core.config import settings
from app.db.redis import redis_store


PASSWORD_SALT = "joey@zhou"


def md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def encrypt_password(raw_password: str) -> str:
    return md5_hex(f"{raw_password}{PASSWORD_SALT}")


def verify_password(raw_password: str, encrypted_password: str) -> bool:
    return encrypt_password(raw_password) == encrypted_password


class TokenManager:
    def __init__(self) -> None:
        self.token_ttl = settings.token_timeout_seconds

    def _token_key(self, token: str) -> str:
        return f"token:{token}"

    def _user_tokens_key(self, user_id: int) -> str:
        return f"user_tokens:{user_id}"

    def create_token(self, user_id: int) -> str:
        token = str(uuid.uuid4())
        redis_store.set(self._token_key(token), str(user_id), ex=self.token_ttl)
        redis_store.sadd(self._user_tokens_key(user_id), token)
        return token

    def get_user_id(self, token: str) -> Optional[int]:
        if not token:
            return None
        value = redis_store.get(self._token_key(token))
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def revoke_token(self, token: str) -> None:
        user_id = self.get_user_id(token)
        redis_store.delete(self._token_key(token))
        if user_id is not None:
            redis_store.srem(self._user_tokens_key(user_id), token)

    def refresh_token(self, token: str) -> Optional[str]:
        user_id = self.get_user_id(token)
        if user_id is None:
            return None
        self.revoke_token(token)
        return self.create_token(user_id)


_token_manager = TokenManager()


def token_manager() -> TokenManager:
    return _token_manager


def parse_bearer_token(auth_header: str | None) -> Optional[str]:
    if not auth_header:
        return None
    if auth_header.startswith(f"{settings.token_prefix} "):
        return auth_header[len(settings.token_prefix) + 1 :].strip()
    return auth_header.strip()


__all__ = [
    "encrypt_password",
    "verify_password",
    "token_manager",
    "parse_bearer_token",
]
