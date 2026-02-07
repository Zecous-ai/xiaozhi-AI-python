from __future__ import annotations

from typing import Dict, List, Optional

from app.db.database import db


class SysTemplateService:
    def query(self, user_id: int, template_name: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
        where = ["state = 1", "userId = :userId"]
        params = {"userId": user_id}
        if template_name:
            where.append("templateName LIKE :templateName")
            params["templateName"] = f"%{template_name}%"
        if category:
            where.append("category = :category")
            params["category"] = category
        sql = (
            "SELECT userId, templateId, templateName, templateDesc, templateContent, category, isDefault, state, createTime, updateTime "
            f"FROM sys_template WHERE {' AND '.join(where)} ORDER BY isDefault, createTime DESC"
        )
        return db().fetch_all(sql, params)

    def select_by_id(self, template_id: int) -> Optional[Dict]:
        sql = (
            "SELECT userId, templateId, templateName, templateDesc, templateContent, category, isDefault, state, createTime, updateTime "
            "FROM sys_template WHERE templateId = :templateId"
        )
        return db().fetch_one(sql, {"templateId": template_id})

    def add(self, template: Dict) -> int:
        sql = (
            "INSERT INTO sys_template (userId, templateName, templateDesc, templateContent, category, createTime, updateTime) "
            "VALUES (:userId, :templateName, :templateDesc, :templateContent, :category, now(), now())"
        )
        return db().execute(sql, template)

    def update(self, template: Dict) -> int:
        sets = []
        params = {"templateId": template.get("templateId"), "userId": template.get("userId")}
        for key in ["templateName", "templateDesc", "templateContent", "category", "isDefault", "state"]:
            if template.get(key) is not None:
                sets.append(f"{key} = :{key}")
                params[key] = template.get(key)
        if not sets:
            return 0
        sql = f"UPDATE sys_template SET {', '.join(sets)} WHERE templateId = :templateId and userId = :userId"
        return db().execute(sql, params)

    def reset_default(self, user_id: int) -> int:
        return db().execute("UPDATE sys_template SET isDefault = '0' WHERE isDefault = 1 AND userId = :userId", {"userId": user_id})

    def delete(self, template_id: int) -> int:
        return db().execute("UPDATE sys_template SET state = '0' WHERE templateId = :templateId", {"templateId": template_id})


__all__ = ["SysTemplateService"]
