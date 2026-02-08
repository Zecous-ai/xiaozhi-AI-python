from __future__ import annotations

from typing import Dict, List, Optional

from app.db.database import db
from app.utils.pagination import build_page


class SysTemplateService:
    @staticmethod
    def _is_default_enabled(value) -> bool:
        return str(value) == "1"

    def query(
        self,
        user_id: int,
        template_name: Optional[str] = None,
        category: Optional[str] = None,
        page_num: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> List[Dict] | Dict:
        where = ["state = 1", "userId = :userId"]
        params = {"userId": user_id}
        if template_name:
            where.append("templateName LIKE :templateName")
            params["templateName"] = f"%{template_name}%"
        if category:
            where.append("category = :category")
            params["category"] = category
        where_sql = " AND ".join(where)
        base_sql = (
            "SELECT userId, templateId, templateName, templateDesc, templateContent, category, isDefault, state, createTime, updateTime "
            f"FROM sys_template WHERE {where_sql} ORDER BY isDefault, createTime DESC"
        )
        if page_num is not None and page_size is not None:
            normalized_page = page_num if page_num > 0 else 1
            normalized_size = page_size if page_size > 0 else 10
            total_sql = f"SELECT count(*) FROM sys_template WHERE {where_sql}"
            total = db().fetch_value(total_sql, params) or 0
            page_sql = base_sql + " LIMIT :limit OFFSET :offset"
            page_params = {**params, "limit": normalized_size, "offset": (normalized_page - 1) * normalized_size}
            rows = db().fetch_all(page_sql, page_params)
            return build_page(rows, int(total), normalized_page, normalized_size)
        return db().fetch_all(base_sql, params)

    def select_by_id(self, template_id: int) -> Optional[Dict]:
        sql = (
            "SELECT userId, templateId, templateName, templateDesc, templateContent, category, isDefault, state, createTime, updateTime "
            "FROM sys_template WHERE templateId = :templateId"
        )
        return db().fetch_one(sql, {"templateId": template_id})

    def add(self, template: Dict) -> int:
        if self._is_default_enabled(template.get("isDefault")):
            self.reset_default(int(template.get("userId")))
        sql = (
            "INSERT INTO sys_template (userId, templateName, templateDesc, templateContent, category, createTime, updateTime) "
            "VALUES (:userId, :templateName, :templateDesc, :templateContent, :category, now(), now())"
        )
        return db().execute(sql, template)

    def update(self, template: Dict) -> int:
        if self._is_default_enabled(template.get("isDefault")):
            self.reset_default(int(template.get("userId")))
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
