from __future__ import annotations

from typing import Dict, List, Optional
import random

from app.db.database import db
from app.utils.pagination import build_page


class SysDeviceService:
    def _build_query_conditions(self, filters: Dict) -> tuple[str, Dict]:
        where = ["1=1"]
        params: Dict = {}
        if filters.get("userId"):
            where.append("sys_device.userId = :userId")
            params["userId"] = filters["userId"]
        if filters.get("deviceId"):
            where.append("sys_device.deviceId = :deviceId")
            params["deviceId"] = filters["deviceId"]
        if filters.get("deviceName"):
            where.append("sys_device.deviceName LIKE :deviceName")
            params["deviceName"] = f"%{filters['deviceName']}%"
        if filters.get("roleName"):
            where.append("sys_role.roleName LIKE :roleName")
            params["roleName"] = f"%{filters['roleName']}%"
        if filters.get("state"):
            where.append("sys_device.state = :state")
            params["state"] = filters["state"]
        if filters.get("roleId"):
            where.append("sys_device.roleId = :roleId")
            params["roleId"] = filters["roleId"]
        return " AND ".join(where), params

    def _select_sql(self, where_sql: str) -> str:
        return (
            "SELECT sys_device.deviceId, sys_device.deviceName, sys_device.ip, sys_device.wifiName, "
            "sys_device.chipModelName, sys_device.type, sys_device.version, sys_device.state, "
            "sys_device.roleId, sys_device.userId, sys_device.lastLogin, sys_device.createTime, sys_device.location, "
            "sys_role.roleName, sys_role.roleDesc, sys_role.voiceName, sys_role.modelId, sys_role.sttId, sys_role.ttsId, "
            "sys_role.vadSpeechTh, sys_role.vadSilenceTh, sys_role.vadEnergyTh, sys_role.vadSilenceMs, "
            "(SELECT COUNT(*) FROM sys_message WHERE sys_message.deviceId = sys_device.deviceId AND sys_message.state = '1') AS totalMessage "
            "FROM sys_device LEFT JOIN sys_role ON sys_device.roleId = sys_role.roleId "
            f"WHERE {where_sql} "
        )

    def query(self, filters: Dict, page_num: int, page_size: int) -> Dict:
        where_sql, params = self._build_query_conditions(filters)
        total_sql = f"SELECT count(*) FROM sys_device LEFT JOIN sys_role ON sys_device.roleId = sys_role.roleId WHERE {where_sql}"
        total = db().fetch_value(total_sql, params) or 0

        sql = self._select_sql(where_sql) + "ORDER BY sys_device.createTime DESC LIMIT :limit OFFSET :offset"
        params.update({"limit": page_size, "offset": (page_num - 1) * page_size})
        rows = db().fetch_all(sql, params)
        return build_page(rows, int(total), page_num, page_size)

    def query_all(self, filters: Dict) -> List[Dict]:
        where_sql, params = self._build_query_conditions(filters)
        sql = self._select_sql(where_sql) + "ORDER BY sys_device.createTime DESC"
        return db().fetch_all(sql, params)

    def select_device_by_id(self, device_id: str) -> Optional[Dict]:
        sql = (
            "SELECT deviceId, deviceName, ip, wifiName, chipModelName, type, version, state, roleId, userId, "
            "lastLogin, createTime, location FROM sys_device WHERE deviceId = :deviceId"
        )
        return db().fetch_one(sql, {"deviceId": device_id})

    def query_verify_code(self, device_id: Optional[str] = None, session_id: Optional[str] = None, code: Optional[str] = None) -> Optional[Dict]:
        where = ["1=1"]
        params = {}
        if device_id:
            where.append("deviceId = :deviceId")
            params["deviceId"] = device_id
        if session_id:
            where.append("sessionId = :sessionId")
            params["sessionId"] = session_id
        if code:
            where.append("code = :code")
            params["code"] = code
        where.append("createTime >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)")
        sql = f"SELECT code, audioPath, deviceId, type FROM sys_code WHERE {' AND '.join(where)} ORDER BY createTime DESC LIMIT 1"
        return db().fetch_one(sql, params)

    def generate_code(self, device_id: str, session_id: Optional[str], device_type: Optional[str]) -> Dict:
        existing = self.query_verify_code(device_id=device_id, session_id=session_id)
        if existing:
            return existing
        code = f"{random.randint(0, 999999):06d}"
        sql = "INSERT INTO sys_code (deviceId, sessionId, type, code, createTime) VALUES (:deviceId, :sessionId, :type, :code, NOW())"
        db().execute(sql, {"deviceId": device_id, "sessionId": session_id, "type": device_type, "code": code})
        return {"code": code}

    def update_code(self, device_id: str, session_id: str, code: str, audio_path: str) -> int:
        sql = (
            "UPDATE sys_code SET audioPath = :audioPath WHERE deviceId = :deviceId AND sessionId = :sessionId AND code = :code"
        )
        return db().execute(sql, {"audioPath": audio_path, "deviceId": device_id, "sessionId": session_id, "code": code})

    def update(self, device: Dict) -> int:
        sets = []
        params = {}
        for key in ["state", "deviceName", "wifiName", "chipModelName", "type", "version", "ip", "roleId", "location"]:
            if device.get(key) not in (None, ""):
                sets.append(f"{key} = :{key}")
                params[key] = device.get(key)
        if device.get("lastLogin") is not None:
            sets.append("lastLogin = NOW()")
        if not sets:
            return 0
        where = []
        if device.get("userId"):
            where.append("userId = :userId")
            params["userId"] = device.get("userId")
        if device.get("deviceId"):
            where.append("deviceId = :deviceId")
            params["deviceId"] = device.get("deviceId")
        sql = f"UPDATE sys_device SET {', '.join(sets)} WHERE {' AND '.join(where)}"
        return db().execute(sql, params)

    def add(self, device: Dict) -> int:
        sql = (
            "INSERT INTO sys_device (deviceId, deviceName, type, userId, roleId) VALUES (:deviceId, :deviceName, :type, :userId, :roleId)"
        )
        return db().execute(
            sql,
            {
                "deviceId": device.get("deviceId"),
                "deviceName": device.get("deviceName"),
                "type": device.get("type"),
                "userId": device.get("userId"),
                "roleId": device.get("roleId"),
            },
        )

    def delete(self, device_id: str, user_id: int) -> int:
        sql = "DELETE FROM sys_device WHERE deviceId = :deviceId AND userId = :userId"
        return db().execute(sql, {"deviceId": device_id, "userId": user_id})

    def delete_messages_for_device(self, device_id: str, user_id: int) -> int:
        sql = (
            "UPDATE sys_message INNER JOIN sys_device ON sys_message.deviceId = sys_device.deviceId "
            "SET sys_message.state = '0' WHERE sys_device.userId = :userId AND sys_message.state = '1' AND sys_message.deviceId = :deviceId"
        )
        return db().execute(sql, {"userId": user_id, "deviceId": device_id})

    def batch_update(self, device_ids: List[str], user_id: int, role_id: Optional[int]) -> int:
        success = 0
        for device_id in device_ids:
            device = {"deviceId": device_id.strip(), "userId": user_id}
            if role_id is not None:
                device["roleId"] = role_id
            success += self.update(device)
        return success


__all__ = ["SysDeviceService"]
