from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from app.core.config import settings
from app.dialogue.token_service import TokenServiceFactory
from app.dialogue.tts.providers import (
    AliyunNlsTtsService,
    AliyunTtsService,
    EdgeTtsService,
    MiniMaxTtsService,
    VolcengineTtsService,
    XfyunTtsService,
)

logger = logging.getLogger("tts_factory")


class TtsServiceFactory:
    OUTPUT_PATH = "audio/"
    DEFAULT_PROVIDER = "edge"
    DEFAULT_VOICE = "zh-CN-XiaoyiNeural"

    def __init__(self, token_factory: TokenServiceFactory | None = None) -> None:
        self._cache: Dict[str, object] = {}
        self._token_factory = token_factory or TokenServiceFactory()

    def _cache_key(self, provider: str, config_id: int | None, voice: str, pitch: float, speed: float) -> str:
        return f"{provider}:{config_id or -1}:{voice}:{pitch}:{speed}"

    def get_default_tts_service(self):
        config = {"provider": self.DEFAULT_PROVIDER}
        return self.get_tts_service(config, self.DEFAULT_VOICE, 1.0, 1.0)

    def get_tts_service(self, config: dict | None, voice_name: str, pitch: float, speed: float):
        cfg = config or {"provider": self.DEFAULT_PROVIDER}
        provider = (cfg.get("provider") or self.DEFAULT_PROVIDER).lower()
        key = self._cache_key(provider, cfg.get("configId"), voice_name, pitch, speed)
        if key in self._cache:
            return self._cache[key]
        service = self._create_service(provider, cfg, voice_name, pitch, speed)
        self._cache[key] = service
        return service

    def _create_service(self, provider: str, config: dict, voice_name: str, pitch: float, speed: float):
        output_path = settings.audio_path or self.OUTPUT_PATH
        Path(output_path).mkdir(parents=True, exist_ok=True)
        if provider == "aliyun":
            return AliyunTtsService(config, voice_name, pitch, speed, output_path)
        if provider in ("aliyun-nls", "aliyun_nls"):
            token_service = self._token_factory.get_token_service(config)
            return AliyunNlsTtsService(config, voice_name, pitch, speed, output_path, token_service)
        if provider == "volcengine":
            return VolcengineTtsService(config, voice_name, pitch, speed, output_path)
        if provider == "xfyun":
            return XfyunTtsService(config, voice_name, pitch, speed, output_path)
        if provider == "minimax":
            return MiniMaxTtsService(config, voice_name, pitch, speed, output_path)
        return EdgeTtsService(voice_name, pitch, speed, output_path)

    def remove_cache(self, config: dict) -> None:
        if not config:
            return
        provider = (config.get("provider") or "").lower()
        config_id = str(config.get("configId"))
        keys = [k for k in self._cache if k.startswith(f"{provider}:{config_id}:")]
        for key in keys:
            self._cache.pop(key, None)


__all__ = ["TtsServiceFactory"]
