from __future__ import annotations

import time
from typing import Any, Dict, Optional, Set

from redis import Redis

from app.core.config import settings


class _MemoryStore:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._expire: Dict[str, float] = {}
        self._sets: Dict[str, Set[str]] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired_keys = [k for k, exp in self._expire.items() if exp <= now]
        for k in expired_keys:
            self._data.pop(k, None)
            self._expire.pop(k, None)

    def get(self, key: str) -> Optional[str]:
        self._cleanup()
        value = self._data.get(key)
        if value is None:
            return None
        return str(value)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        self._data[key] = value
        if ex is not None:
            self._expire[key] = time.time() + ex
        return True

    def delete(self, key: str) -> int:
        existed = 1 if key in self._data else 0
        self._data.pop(key, None)
        self._expire.pop(key, None)
        return existed

    def sadd(self, key: str, *values: str) -> int:
        s = self._sets.setdefault(key, set())
        before = len(s)
        s.update(values)
        return len(s) - before

    def srem(self, key: str, *values: str) -> int:
        s = self._sets.get(key, set())
        before = len(s)
        for v in values:
            s.discard(v)
        return before - len(s)

    def smembers(self, key: str) -> Set[str]:
        return set(self._sets.get(key, set()))


class RedisStore:
    def __init__(self) -> None:
        self._client: Redis | None = None
        self._memory = _MemoryStore()
        try:
            self._client = Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
            )
            self._client.ping()
        except Exception:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Optional[str]:
        if self._client is None:
            return self._memory.get(key)
        return self._client.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        if self._client is None:
            return self._memory.set(key, value, ex=ex)
        return bool(self._client.set(name=key, value=value, ex=ex))

    def delete(self, key: str) -> int:
        if self._client is None:
            return self._memory.delete(key)
        return int(self._client.delete(key))

    def sadd(self, key: str, *values: str) -> int:
        if self._client is None:
            return self._memory.sadd(key, *values)
        return int(self._client.sadd(key, *values))

    def srem(self, key: str, *values: str) -> int:
        if self._client is None:
            return self._memory.srem(key, *values)
        return int(self._client.srem(key, *values))

    def smembers(self, key: str) -> Set[str]:
        if self._client is None:
            return self._memory.smembers(key)
        return set(self._client.smembers(key))


redis_store = RedisStore()

__all__ = ["redis_store", "RedisStore"]
