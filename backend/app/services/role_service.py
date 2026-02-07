from __future__ import annotations

from typing import Dict, List, Optional

from app.db.database import db
from app.utils.pagination import build_page


class SysRoleService:
    def query(self, filters: Dict, page_num: int | None = None, page_size: int | None = None) -> Dict | List[Dict]:
        where = ["sys_role.state = 1"]
        params = {}
        if filters.get("userId"):
            where.append("sys_role.userId = :userId")
            params["userId"] = filters["userId"]
        if filters.get("roleId"):
            where.append("sys_role.roleId = :roleId")
            params["roleId"] = filters["roleId"]
        if filters.get("roleName"):
            where.append("sys_role.roleName LIKE :roleName")
            params["roleName"] = f"%{filters['roleName']}%"
        if filters.get("isDefault"):
            where.append("sys_role.isDefault = :isDefault")
            params["isDefault"] = filters["isDefault"]

        where_sql = " AND ".join(where)
        base_sql = (
            "SELECT sys_role.roleId, sys_role.avatar, sys_role.roleName, sys_role.roleDesc, sys_role.voiceName, "
            "sys_role.ttsPitch, sys_role.ttsSpeed, sys_role.modelId, sys_role.sttId, sys_role.ttsId, sys_role.memoryType, "
            "sys_role.temperature, sys_role.topP, sys_role.vadSpeechTh, sys_role.vadSilenceTh, sys_role.vadEnergyTh, "
            "sys_role.vadSilenceMs, sys_role.userId, sys_role.state, sys_role.isDefault, sys_role.createTime, "
            "model_config.configName AS modelName, model_config.provider AS modelProvider, "
            "stt_config.configName AS sttName, stt_config.configDesc AS sttDesc, "
            "tts_config.provider AS ttsProvider, "
            "(SELECT COUNT(*) FROM sys_device WHERE sys_device.roleId = sys_role.roleId) AS totalDevice "
            "FROM sys_role "
            "LEFT JOIN sys_config tts_config ON sys_role.ttsId = tts_config.configId AND tts_config.configType = 'tts' "
            "LEFT JOIN sys_config model_config ON sys_role.modelId = model_config.configId AND model_config.configType = 'llm' "
            "LEFT JOIN sys_config stt_config ON sys_role.sttId = stt_config.configId AND stt_config.configType = 'stt' "
            f"WHERE {where_sql} GROUP BY sys_role.roleId"
        )

        if page_num and page_size:
            total_sql = f"SELECT count(*) FROM sys_role WHERE {where_sql}"
            total = db().fetch_value(total_sql, params) or 0
            sql = base_sql + " LIMIT :limit OFFSET :offset"
            params.update({"limit": page_size, "offset": (page_num - 1) * page_size})
            rows = db().fetch_all(sql, params)
            return build_page(rows, int(total), page_num, page_size)
        return db().fetch_all(base_sql, params)

    def select_role_by_id(self, role_id: int) -> Optional[Dict]:
        sql = (
            "SELECT roleId, avatar, roleName, roleDesc, voiceName, ttsPitch, ttsSpeed, modelId, sttId, ttsId, memoryType, "
            "temperature, topP, vadSpeechTh, vadSilenceTh, vadEnergyTh, vadSilenceMs, userId, state, isDefault, createTime "
            "FROM sys_role WHERE roleId = :roleId"
        )
        return db().fetch_one(sql, {"roleId": role_id})

    def add(self, role: Dict) -> int:
        sql = (
            "INSERT INTO sys_role (avatar, roleName, roleDesc, voiceName, ttsPitch, ttsSpeed, modelId, ttsId, sttId, memoryType, "
            "temperature, topP, userId, isDefault) VALUES (:avatar, :roleName, :roleDesc, :voiceName, :ttsPitch, :ttsSpeed, :modelId, "
            ":ttsId, :sttId, :memoryType, :temperature, :topP, :userId, :isDefault)"
        )
        return db().execute(sql, role)

    def update(self, role: Dict) -> int:
        sets = ["avatar = :avatar"]
        params = {"avatar": role.get("avatar")}
        for key in [
            "roleName",
            "roleDesc",
            "voiceName",
            "isDefault",
            "modelId",
            "ttsId",
            "sttId",
            "state",
            "temperature",
            "topP",
            "vadEnergyTh",
            "vadSpeechTh",
            "vadSilenceTh",
            "vadSilenceMs",
            "ttsPitch",
            "ttsSpeed",
            "memoryType",
        ]:
            if key in role and role[key] is not None and role[key] != "":
                sets.append(f"{key} = :{key}")
                params[key] = role[key]
        params["roleId"] = role.get("roleId")
        sql = f"UPDATE sys_role SET {', '.join(sets)} WHERE roleId = :roleId"
        return db().execute(sql, params)

    def reset_default(self, user_id: int) -> int:
        return db().execute("UPDATE sys_role SET isDefault = '0' WHERE userId = :userId", {"userId": user_id})

    def delete(self, role_id: int) -> int:
        return db().execute("DELETE FROM sys_role WHERE roleId = :roleId", {"roleId": role_id})


__all__ = ["SysRoleService"]
