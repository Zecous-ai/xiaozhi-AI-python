from __future__ import annotations

from typing import Dict, Optional

from app.db.database import db


class SysAuthRoleService:
    def select_by_id(self, role_id: int) -> Optional[Dict]:
        sql = (
            "SELECT roleId, roleName, roleKey, description, status, createTime, updateTime "
            "FROM sys_auth_role WHERE roleId = :roleId"
        )
        return db().fetch_one(sql, {"roleId": role_id})


__all__ = ["SysAuthRoleService"]
