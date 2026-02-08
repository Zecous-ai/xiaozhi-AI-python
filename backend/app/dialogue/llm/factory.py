from __future__ import annotations

import logging
from typing import Dict

from app.dialogue.llm.openai_compatible import OpenAICompatibleModel
from app.services.config_service import SysConfigService
from app.services.role_service import SysRoleService

logger = logging.getLogger("chat_model_factory")


class ChatModelFactory:
    def __init__(self, config_service: SysConfigService, role_service: SysRoleService) -> None:
        self.config_service = config_service
        self.role_service = role_service

    def take_chat_model(self, session) -> OpenAICompatibleModel:
        device = session.sys_device or {}
        role_id = device.get("roleId")
        role = self.role_service.select_role_by_id(int(role_id)) if role_id else None
        return self._create_for_role(role)

    def take_chat_model_by_role(self, role_id: int) -> OpenAICompatibleModel:
        role = self.role_service.select_role_by_id(role_id)
        return self._create_for_role(role)

    def take_vision_model(self) -> OpenAICompatibleModel:
        config = self.config_service.select_model_type("vision")
        if not config:
            raise ValueError("未配置视觉模型")
        return self._create_model(config, {})

    def take_intent_model(self) -> OpenAICompatibleModel:
        config = self.config_service.select_model_type("intent")
        if not config:
            raise ValueError("未配置意图模型")
        return self._create_model(config, {})

    def _create_for_role(self, role: Dict | None) -> OpenAICompatibleModel:
        if not role or not role.get("modelId"):
            raise ValueError("角色未配置模型")
        config = self.config_service.select_config_by_id(int(role.get("modelId")))
        return self._create_model(config, role)

    def _create_model(self, config: Dict | None, role: Dict | None) -> OpenAICompatibleModel:
        if not config:
            raise ValueError("模型配置不存在")
        provider = (config.get("provider") or "openai").lower()
        endpoint = config.get("apiUrl") or "https://api.openai.com/v1"
        api_key = config.get("apiKey") or ""
        model = config.get("configName") or config.get("modelType") or "gpt-3.5-turbo"
        temperature = (role or {}).get("temperature")
        top_p = (role or {}).get("topP")
        if provider not in (
            "openai",
            "openai-compatible",
            "zhipuai",
            "ollama",
            "openrouter",
            "volcengine",
            "xingchen",
            "xinghuo",
            "coze",
            "dify",
        ):
            logger.warning("未知provider %s，使用OpenAI兼容协议", provider)
        return OpenAICompatibleModel(endpoint, api_key, model, temperature, top_p)


__all__ = ["ChatModelFactory"]
