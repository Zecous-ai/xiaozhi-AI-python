from __future__ import annotations

import logging
from typing import Dict

from app.dialogue.stt.base import SttService
from app.dialogue.stt.providers import (
    AliyunNlsSttService,
    AliyunSttService,
    FunASRSttService,
    TencentSttService,
    VoskSttService,
    XfyunSttService,
)
from app.dialogue.token_service import TokenServiceFactory

logger = logging.getLogger("stt_factory")


class SttServiceFactory:
    def __init__(self, token_factory: TokenServiceFactory | None = None) -> None:
        self._cache: Dict[str, SttService] = {}
        self._token_factory = token_factory or TokenServiceFactory()

    def _cache_key(self, provider: str, config_id: int | None) -> str:
        return f"{provider}:{config_id or -1}"

    def get_default_stt_service(self) -> SttService:
        return VoskSttService()

    def get_stt_service(self, config: dict | None) -> SttService:
        if not config:
            return self.get_default_stt_service()
        provider = (config.get("provider") or "vosk").lower()
        cache_key = self._cache_key(provider, config.get("configId"))
        if cache_key in self._cache:
            return self._cache[cache_key]

        service = self._create_service(provider, config)
        self._cache[cache_key] = service
        return service

    def _create_service(self, provider: str, config: dict) -> SttService:
        if provider in ("aliyun",):
            return AliyunSttService(config)
        if provider in ("aliyun-nls", "aliyun_nls"):
            token_service = self._token_factory.get_token_service(config)
            return AliyunNlsSttService(config, token_service)
        if provider == "tencent":
            return TencentSttService(config)
        if provider == "xfyun":
            return XfyunSttService(config)
        if provider == "funasr":
            return FunASRSttService(config)
        if provider == "vosk":
            return VoskSttService()
        logger.warning("未知 STT 提供商 %s，使用 Vosk", provider)
        return VoskSttService()

    def remove_cache(self, config: dict) -> None:
        if not config:
            return
        provider = config.get("provider") or "vosk"
        cache_key = self._cache_key(provider, config.get("configId"))
        self._cache.pop(cache_key, None)


__all__ = ["SttServiceFactory"]
