from __future__ import annotations

from typing import Dict, Optional

from app.db.database import db


class SysUserAuthService:
    def select_by_openid_and_platform(self, open_id: str, platform: str) -> Optional[Dict]:
        sql = (
            "SELECT id, user_id, open_id, union_id, platform, profile, create_time, update_time "
            "FROM sys_user_auth WHERE open_id = :openId AND platform = :platform LIMIT 1"
        )
        return db().fetch_one(sql, {"openId": open_id, "platform": platform})

    def select_by_userid_and_platform(self, user_id: int, platform: str) -> Optional[Dict]:
        sql = (
            "SELECT id, user_id, open_id, union_id, platform, profile, create_time, update_time "
            "FROM sys_user_auth WHERE user_id = :userId AND platform = :platform LIMIT 1"
        )
        return db().fetch_one(sql, {"userId": user_id, "platform": platform})

    def insert(self, auth: Dict) -> int:
        sql = (
            "INSERT INTO sys_user_auth (user_id, open_id, union_id, platform, profile) "
            "VALUES (:userId, :openId, :unionId, :platform, :profile)"
        )
        return db().execute(sql, auth)

    def update(self, auth: Dict) -> int:
        sets = []
        params = {"id": auth.get("id")}
        for key, column in [
            ("userId", "user_id"),
            ("openId", "open_id"),
            ("unionId", "union_id"),
            ("platform", "platform"),
            ("profile", "profile"),
        ]:
            if auth.get(key) is not None:
                sets.append(f"{column} = :{key}")
                params[key] = auth.get(key)
        if not sets:
            return 0
        sql = f"UPDATE sys_user_auth SET {', '.join(sets)} WHERE id = :id"
        return db().execute(sql, params)


__all__ = ["SysUserAuthService"]
