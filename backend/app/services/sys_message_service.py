from __future__ import annotations

from typing import Dict, List, Optional

from app.db.database import db
from app.utils.pagination import build_page


class SysMessageService:
    def _build_query_conditions(self, filters: Dict) -> tuple[str, Dict]:
        where = ["sys_message.state = 1"]
        params: Dict = {}
        if filters.get("userId"):
            where.append("sys_device.userId = :userId")
            params["userId"] = filters["userId"]
        if filters.get("deviceId"):
            where.append("sys_message.deviceId = :deviceId")
            params["deviceId"] = filters["deviceId"]
        if filters.get("roleId"):
            where.append("sys_message.roleId = :roleId")
            params["roleId"] = filters["roleId"]
        if filters.get("messageType"):
            where.append("sys_message.messageType = :messageType")
            params["messageType"] = filters["messageType"]
        if filters.get("deviceName"):
            where.append("sys_device.deviceName = :deviceName")
            params["deviceName"] = filters["deviceName"]
        if filters.get("startTime") and filters.get("endTime"):
            where.append("sys_message.createTime >= :startTime AND sys_message.createTime <= :endTime")
            params["startTime"] = filters["startTime"]
            params["endTime"] = filters["endTime"]
        if filters.get("sender"):
            where.append("sys_message.sender = :sender")
            params["sender"] = filters["sender"]
        return " AND ".join(where), params

    def _select_sql(self, where_sql: str) -> str:
        return (
            "SELECT sys_message.messageId, sys_message.deviceId, sys_message.message, sys_message.sender, sys_message.roleId, "
            "sys_message.state, sys_message.createTime, sys_message.messageType, sys_device.deviceName, sys_device.userId, sys_role.roleName "
            "FROM sys_message "
            "LEFT JOIN sys_device ON sys_message.deviceId = sys_device.deviceId "
            "LEFT JOIN sys_role ON sys_message.roleId = sys_role.roleId "
            f"WHERE {where_sql} "
        )

    def query(self, filters: Dict, page_num: int, page_size: int) -> Dict:
        where_sql, params = self._build_query_conditions(filters)
        total_sql = (
            "SELECT count(*) FROM sys_message LEFT JOIN sys_device ON sys_message.deviceId = sys_device.deviceId "
            f"WHERE {where_sql}"
        )
        total = db().fetch_value(total_sql, params) or 0

        sql = self._select_sql(where_sql) + "ORDER BY sys_message.createTime DESC, sender DESC LIMIT :limit OFFSET :offset"
        params.update({"limit": page_size, "offset": (page_num - 1) * page_size})
        rows = db().fetch_all(sql, params)
        return build_page(rows, int(total), page_num, page_size)

    def query_all(self, filters: Dict) -> List[Dict]:
        where_sql, params = self._build_query_conditions(filters)
        sql = self._select_sql(where_sql) + "ORDER BY sys_message.createTime DESC, sender DESC"
        return db().fetch_all(sql, params)

    def find(self, device_id: str, role_id: int, limit: int) -> List[Dict]:
        sql = (
            "SELECT messageId, deviceId, message, sender, roleId, state, createTime, messageType "
            "FROM sys_message WHERE sys_message.state = 1 and sys_message.messageType = 'NORMAL' "
            "and sys_message.deviceId = :deviceId and sys_message.roleId = :roleId "
            "ORDER BY sys_message.createTime DESC LIMIT :limit"
        )
        return db().fetch_all(sql, {"deviceId": device_id, "roleId": role_id, "limit": limit})

    def find_after(self, device_id: str, role_id: int, time_millis: str) -> List[Dict]:
        sql = (
            "SELECT messageId, deviceId, message, sender, roleId, state, createTime, messageType "
            "FROM sys_message WHERE sys_message.state = 1 and sys_message.messageType = 'NORMAL' "
            "and sys_message.deviceId = :deviceId and sys_message.roleId = :roleId and sys_message.createTime >= :timeMillis"
        )
        return db().fetch_all(sql, {"deviceId": device_id, "roleId": role_id, "timeMillis": time_millis})

    def add(self, message: Dict) -> int:
        sql = (
            "INSERT INTO sys_message (deviceId, sessionId, sender, roleId, message, messageType, createTime) "
            "SELECT :deviceId, :sessionId, :sender, :roleId, :message, :messageType, :createTime"
        )
        return db().execute(sql, message)

    def save_all(self, messages: List[Dict]) -> int:
        if not messages:
            return 0
        values = []
        params = {}
        for idx, msg in enumerate(messages):
            keys = ["deviceId", "sessionId", "sender", "roleId", "message", "messageType", "createTime"]
            placeholders = []
            for key in keys:
                param_key = f"{key}_{idx}"
                params[param_key] = msg.get(key)
                placeholders.append(f":{param_key}")
            values.append(f"({', '.join(placeholders)})")
        sql = (
            "INSERT INTO sys_message (deviceId, sessionId, sender, roleId, message, messageType, createTime) VALUES "
            + ", ".join(values)
        )
        return db().execute(sql, params)

    def delete(self, user_id: int, message_id: Optional[int] = None, device_id: Optional[str] = None) -> int:
        where = ["sys_device.userId = :userId", "sys_message.state = '1'"]
        params = {"userId": user_id}
        if message_id:
            where.append("sys_message.messageId = :messageId")
            params["messageId"] = message_id
        if device_id:
            where.append("sys_message.deviceId = :deviceId")
            params["deviceId"] = device_id
        sql = (
            "UPDATE sys_message INNER JOIN sys_device ON sys_message.deviceId = sys_device.deviceId "
            f"SET sys_message.state = '0' WHERE {' AND '.join(where)}"
        )
        return db().execute(sql, params)

    def update_message_by_audio_file(self, device_id: str, role_id: int, sender: str, create_time: str, audio_path: str) -> int:
        sql = (
            "UPDATE sys_message SET audioPath = :audioPath "
            "WHERE deviceId = :deviceId AND roleId = :roleId AND sender = :sender AND createTime = :createTime"
        )
        return db().execute(
            sql,
            {
                "audioPath": audio_path,
                "deviceId": device_id,
                "roleId": role_id,
                "sender": sender,
                "createTime": create_time,
            },
        )

    def update_message_type(self, device_id: str, role_id: int, sender: str, create_time: str, message_type: str) -> int:
        sql = (
            "UPDATE sys_message SET messageType = :messageType "
            "WHERE deviceId = :deviceId AND roleId = :roleId AND sender = :sender AND createTime = :createTime"
        )
        return db().execute(
            sql,
            {
                "messageType": message_type,
                "deviceId": device_id,
                "roleId": role_id,
                "sender": sender,
                "createTime": create_time,
            },
        )


__all__ = ["SysMessageService"]
