from __future__ import annotations

from typing import Dict, List

from app.db.database import db


class SysPermissionService:
    def select_by_user_id(self, user_id: int) -> List[Dict]:
        sql = (
            "SELECT DISTINCT p.* FROM sys_permission p "
            "INNER JOIN sys_role_permission rp ON p.permissionId = rp.permissionId "
            "INNER JOIN sys_user u ON rp.roleId = u.roleId "
            "WHERE u.userId = :userId AND p.status = '1' ORDER BY p.sort"
        )
        return db().fetch_all(sql, {"userId": user_id})

    def build_permission_tree(self, permissions: List[Dict]) -> List[Dict]:
        by_id = {p["permissionId"]: {**p, "children": []} for p in permissions}
        root = []
        for perm in by_id.values():
            parent_id = perm.get("parentId")
            if parent_id and parent_id in by_id:
                by_id[parent_id]["children"].append(perm)
            else:
                root.append(perm)
        return root


__all__ = ["SysPermissionService"]
