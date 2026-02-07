from __future__ import annotations

from typing import Dict, List, Optional

from app.db.database import db


class SysConfigService:
    def query(self, filters: Dict) -> List[Dict]:
        where = ["state = '1'"]
        params = {}
        if filters.get("userId"):
            where.append("userId = :userId")
            params["userId"] = filters["userId"]
        if filters.get("isDefault"):
            where.append("isDefault = :isDefault")
            params["isDefault"] = filters["isDefault"]
        if filters.get("configType"):
            where.append("configType = :configType")
            params["configType"] = filters["configType"]
        if filters.get("modelType"):
            where.append("modelType = :modelType")
            params["modelType"] = filters["modelType"]
        if filters.get("provider"):
            where.append("provider = :provider")
            params["provider"] = filters["provider"]
        else:
            where.append("provider != 'coze'")
            where.append("provider != 'dify'")
            where.append("provider != 'xingchen'")
        if filters.get("configName"):
            where.append("configName LIKE :configName")
            params["configName"] = f"%{filters['configName']}%"

        sql = (
            "SELECT DISTINCT configId, userId, configName, configDesc, configType, modelType, provider, appId, apiKey, apiSecret, ak, sk, apiUrl, isDefault, state, createTime "
            f"FROM sys_config WHERE {' AND '.join(where)}"
        )
        return db().fetch_all(sql, params)

    def select_config_by_id(self, config_id: int) -> Optional[Dict]:
        sql = (
            "SELECT configId, userId, configName, configDesc, configType, modelType, provider, appId, apiKey, apiSecret, ak, sk, apiUrl, isDefault, state, createTime "
            "FROM sys_config WHERE configId = :configId"
        )
        return db().fetch_one(sql, {"configId": config_id})

    def select_model_type(self, model_type: str) -> Optional[Dict]:
        sql = (
            "SELECT configId, userId, configName, configDesc, configType, modelType, provider, appId, apiKey, apiSecret, ak, sk, apiUrl, isDefault, state, createTime "
            "FROM sys_config WHERE modelType = :modelType AND state = '1' LIMIT 1"
        )
        return db().fetch_one(sql, {"modelType": model_type})

    def add(self, config: Dict) -> int:
        sql = (
            "INSERT INTO sys_config (userId, configType, modelType, provider, configName, configDesc, appId, apiKey, apiSecret, ak, sk, apiUrl, isDefault) "
            "VALUES (:userId, :configType, :modelType, :provider, :configName, :configDesc, :appId, :apiKey, :apiSecret, :ak, :sk, :apiUrl, :isDefault)"
        )
        return db().execute(sql, config)

    def update(self, config: Dict) -> int:
        sets = []
        params = {"configId": config.get("configId")}
        for key in [
            "configType",
            "modelType",
            "provider",
            "configName",
            "configDesc",
            "appId",
            "apiKey",
            "apiSecret",
            "ak",
            "sk",
            "apiUrl",
            "isDefault",
            "state",
        ]:
            if config.get(key) not in (None, ""):
                sets.append(f"{key} = :{key}")
                params[key] = config.get(key)
        if not sets:
            return 0
        sql = f"UPDATE sys_config SET {', '.join(sets)} WHERE configId = :configId"
        return db().execute(sql, params)

    def reset_default(self, config_type: str, user_id: int, model_type: Optional[str] = None) -> int:
        where = "configType = :configType AND userId = :userId"
        params = {"configType": config_type, "userId": user_id}
        if model_type:
            where += " AND modelType = :modelType"
            params["modelType"] = model_type
        sql = f"UPDATE sys_config SET isDefault = '0' WHERE {where}"
        return db().execute(sql, params)


__all__ = ["SysConfigService"]
