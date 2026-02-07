from __future__ import annotations

import logging
from typing import Dict, List

import httpx

from app.dialogue.token_service import CozeTokenService
from app.services.config_service import SysConfigService

logger = logging.getLogger("agent_service")


class SysAgentService:
    def __init__(self, config_service: SysConfigService) -> None:
        self.config_service = config_service

    def query(self, agent: Dict) -> List[Dict]:
        provider = (agent.get("provider") or "").lower()
        if provider == "coze":
            return self._get_coze_agents(agent)
        if provider == "dify":
            return self._get_dify_agents(agent)
        if provider == "xingchen":
            return self._get_xingchen_agents(agent)
        return []

    def _get_dify_agents(self, agent: Dict) -> List[Dict]:
        agent_list: List[Dict] = []
        configs = self.config_service.query({"provider": "dify"})
        if not configs:
            return agent_list
        agent_configs = [c for c in configs if c.get("configType") == "agent"]
        llm_config_map = {c.get("apiKey"): c for c in configs if c.get("configType") == "llm" and c.get("apiKey")}

        for cfg in agent_configs:
            api_key = cfg.get("apiKey")
            api_url = cfg.get("apiUrl")
            user_id = cfg.get("userId")
            existing = llm_config_map.get(api_key)
            if existing:
                agent_item = {
                    "configId": existing.get("configId"),
                    "provider": "dify",
                    "apiKey": api_key,
                    "agentName": existing.get("configName"),
                    "agentDesc": existing.get("configDesc"),
                    "isDefault": existing.get("isDefault"),
                    "publishTime": existing.get("createTime"),
                }
                if agent.get("agentName"):
                    if agent_item["agentName"] and agent.get("agentName").lower() in agent_item["agentName"].lower():
                        agent_list.append(agent_item)
                else:
                    agent_list.append(agent_item)
                continue

            agent_item = {
                "configId": cfg.get("configId"),
                "provider": "dify",
                "apiKey": api_key,
            }
            try:
                info = httpx.get(f"{api_url}/info", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
                if info.status_code == 200:
                    info_json = info.json()
                    agent_item["agentName"] = info_json.get("name") or "DIFY Agent"
                    agent_item["agentDesc"] = info_json.get("description") or ""
                else:
                    agent_item["agentName"] = cfg.get("configName") or "DIFY Agent"
                    agent_item["agentDesc"] = "无法连接 DIFY API"

                meta = httpx.get(f"{api_url}/meta", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
                if meta.status_code == 200:
                    meta_json = meta.json()
                    icon = meta_json.get("tool_icons", {}).get("api_tool", {}).get("content")
                    if icon:
                        agent_item["iconUrl"] = icon

                new_llm = {
                    "userId": user_id,
                    "configType": "llm",
                    "provider": "dify",
                    "apiKey": api_key,
                    "configName": agent_item.get("agentName"),
                    "configDesc": agent_item.get("agentDesc"),
                    "apiUrl": api_url,
                    "state": "1",
                }
                self.config_service.add(new_llm)
            except Exception as exc:
                logger.error("DIFY 获取失败: %s", exc)
                agent_item["agentName"] = cfg.get("configName") or "DIFY Agent"
                agent_item["agentDesc"] = "无法连接 DIFY API"

            if agent.get("agentName"):
                if agent_item.get("agentName") and agent.get("agentName").lower() in agent_item["agentName"].lower():
                    agent_list.append(agent_item)
            else:
                agent_list.append(agent_item)

        return agent_list

    def _get_xingchen_agents(self, agent: Dict) -> List[Dict]:
        agent_list: List[Dict] = []
        configs = self.config_service.query({"provider": "xingchen"})
        if not configs:
            return agent_list
        agent_configs = [c for c in configs if c.get("configType") == "agent"]
        llm_config_map = {c.get("apiKey"): c for c in configs if c.get("configType") == "llm" and c.get("apiKey")}

        for cfg in agent_configs:
            api_key = cfg.get("apiKey")
            api_url = cfg.get("apiUrl")
            user_id = cfg.get("userId")
            existing = llm_config_map.get(api_key)
            if existing:
                agent_list.append(
                    {
                        "configId": existing.get("configId"),
                        "provider": "xingchen",
                        "apiKey": api_key,
                        "agentName": existing.get("configName"),
                        "agentDesc": existing.get("configDesc"),
                        "isDefault": existing.get("isDefault"),
                        "publishTime": existing.get("createTime"),
                    }
                )
                continue

            agent_item = {
                "configId": cfg.get("configId"),
                "provider": "xingchen",
                "apiKey": api_key,
                "agentName": "XingChen Agent",
                "agentDesc": "",
            }
            new_llm = {
                "userId": user_id,
                "configType": "llm",
                "provider": "xingchen",
                "apiKey": api_key,
                "configName": agent_item["agentName"],
                "configDesc": agent_item["agentDesc"],
                "apiUrl": api_url,
                "state": "1",
            }
            try:
                self.config_service.add(new_llm)
            except Exception as exc:
                logger.error("XingChen LLM 配置新增失败: %s", exc)
            agent_list.append(agent_item)

        return agent_list

    def _get_coze_agents(self, agent: Dict) -> List[Dict]:
        agent_list: List[Dict] = []
        configs = self.config_service.query({"provider": "coze"})
        if not configs:
            return agent_list
        config = configs[0]
        space_id = config.get("apiSecret")
        if not space_id:
            return agent_list

        try:
            token_service = CozeTokenService(config)
            token = token_service.get_token()
            url = f"https://api.coze.cn/v1/space/published_bots_list?space_id={space_id}"
            resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if resp.status_code != 200:
                logger.error("Coze API 返回异常: %s", resp.text)
                return agent_list
            data = resp.json()
            if data.get("code") != 0:
                logger.error("Coze API 错误: %s", data.get("msg"))
                return agent_list

            space_bots = data.get("data", {}).get("space_bots", [])
            existing_configs = self.config_service.query({"userId": config.get("userId"), "configType": "llm", "provider": "coze"})
            existing_map = {c.get("configName"): c for c in existing_configs if c.get("configName")}

            for bot in space_bots:
                bot_id = bot.get("bot_id")
                bot_name = bot.get("bot_name")
                description = bot.get("description")
                icon_url = bot.get("icon_url")
                publish_time = bot.get("publish_time")

                agent_item = {
                    "botId": bot_id,
                    "agentName": bot_name,
                    "agentDesc": description,
                    "iconUrl": icon_url,
                    "publishTime": publish_time,
                    "provider": "coze",
                }
                if bot_id in existing_map:
                    existing = existing_map[bot_id]
                    agent_item["configId"] = existing.get("configId")
                    agent_item["isDefault"] = existing.get("isDefault")
                    existing["configDesc"] = description
                    try:
                        self.config_service.update(existing)
                    except Exception as exc:
                        logger.error("更新 Coze 配置失败: %s", exc)
                else:
                    new_config = {
                        "userId": config.get("userId"),
                        "configType": "llm",
                        "provider": "coze",
                        "configName": bot_id,
                        "configDesc": description,
                        "state": "1",
                    }
                    try:
                        self.config_service.add(new_config)
                    except Exception as exc:
                        logger.error("新增 Coze 配置失败: %s", exc)

                if agent.get("agentName"):
                    if bot_name and agent.get("agentName").lower() in bot_name.lower():
                        agent_list.append(agent_item)
                else:
                    agent_list.append(agent_item)

        except Exception as exc:
            logger.error("Coze 请求失败: %s", exc)

        return agent_list


__all__ = ["SysAgentService"]
