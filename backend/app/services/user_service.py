from __future__ import annotations

import random
from typing import Dict, List, Optional

from app.core.security import encrypt_password, verify_password
from app.db.database import db
from app.utils.pagination import build_page


class SysUserService:
    def login(self, username: str, password: str) -> Dict:
        user = self.select_user_by_username(username)
        if not user:
            raise ValueError("UsernameNotFound")
        if not verify_password(password, user.get("password", "")):
            raise ValueError("PasswordNotMatch")
        return user

    def query(self, username: str, start_time: Optional[str], end_time: Optional[str]) -> Optional[Dict]:
        sql = (
            "SELECT sys_user.userId, sys_user.username, sys_user.wxOpenId, sys_user.wxUnionId, "
            "sys_user.`name`, sys_user.tel, sys_user.email, sys_user.avatar, sys_user.password, "
            "sys_user.state, sys_user.isAdmin, sys_user.roleId, sys_user.loginIp, sys_user.loginTime, "
            "sys_user.createTime, "
            "(SELECT count(*) FROM sys_device WHERE sys_device.userId = sys_user.userId) AS totalDevice, "
            "(SELECT count(*) FROM sys_message LEFT JOIN sys_device ON sys_device.deviceId = sys_message.deviceId "
            "WHERE sys_device.userId = sys_user.userId {time_filter}) AS totalMessage, "
            "(SELECT count(*) FROM sys_device WHERE sys_device.userId = sys_user.userId) AS aliveNumber "
            "FROM sys_user WHERE username = :username"
        )
        time_filter = ""
        params = {"username": username}
        if start_time:
            time_filter = "AND sys_message.createTime >= :startTime AND sys_message.createTime <= :endTime"
            params["startTime"] = start_time
            params["endTime"] = end_time
        sql = sql.format(time_filter=time_filter)
        return db().fetch_one(sql, params)

    def query_users(self, filters: Dict, page_num: int, page_size: int) -> Dict:
        where = ["1=1"]
        params = {}
        if filters.get("email"):
            where.append("sys_user.email = :email")
            params["email"] = filters["email"]
        if filters.get("tel"):
            where.append("sys_user.tel = :tel")
            params["tel"] = filters["tel"]
        if filters.get("name"):
            where.append("sys_user.name LIKE :name")
            params["name"] = f"%{filters['name']}%"
        if filters.get("isAdmin"):
            where.append("sys_user.isAdmin = :isAdmin")
            params["isAdmin"] = filters["isAdmin"]

        where_sql = " AND ".join(where)
        total_sql = f"SELECT count(*) FROM sys_user WHERE {where_sql}"
        total = db().fetch_value(total_sql, params) or 0

        query_sql = (
            "SELECT sys_user.userId, sys_user.`name`, sys_user.username, "
            "CASE WHEN LENGTH(sys_user.tel) > 7 THEN CONCAT(LEFT(sys_user.tel,3),'****',RIGHT(sys_user.tel,4)) ELSE sys_user.tel END AS tel, "
            "sys_user.email, sys_user.avatar, sys_user.state, sys_user.isAdmin, sys_user.loginIp, sys_user.loginTime, sys_user.createTime, "
            "(SELECT count(*) FROM sys_device WHERE sys_device.userId = sys_user.userId) AS totalDevice, "
            "(SELECT count(*) FROM sys_message JOIN sys_device ON sys_device.deviceId = sys_message.deviceId "
            "WHERE sys_device.userId = sys_user.userId) AS totalMessage, "
            "(SELECT count(*) FROM sys_device WHERE sys_device.userId = sys_user.userId and sys_device.state = 1) AS aliveNumber "
            f"FROM sys_user WHERE {where_sql} ORDER BY createTime DESC LIMIT :limit OFFSET :offset"
        )
        params.update({"limit": page_size, "offset": (page_num - 1) * page_size})
        rows = db().fetch_all(query_sql, params)
        return build_page(rows, int(total), page_num, page_size)

    def select_user_by_user_id(self, user_id: int) -> Optional[Dict]:
        sql = (
            "SELECT userId, username, wxOpenId, wxUnionId, `name`, tel, email, avatar, password, state, "
            "isAdmin, roleId, loginIp, loginTime, createTime FROM sys_user WHERE userId = :userId"
        )
        return db().fetch_one(sql, {"userId": user_id})

    def select_user_by_username(self, username: str) -> Optional[Dict]:
        sql = (
            "SELECT userId, username, wxOpenId, wxUnionId, `name`, tel, email, avatar, password, state, "
            "isAdmin, roleId, loginIp, loginTime, createTime FROM sys_user WHERE username = :username"
        )
        return db().fetch_one(sql, {"username": username})

    def select_user_by_wx_open_id(self, wx_open_id: str) -> Optional[Dict]:
        sql = (
            "SELECT userId, username, wxOpenId, wxUnionId, `name`, tel, email, avatar, password, state, "
            "isAdmin, roleId, loginIp, loginTime, createTime FROM sys_user WHERE wxOpenId = :wxOpenId"
        )
        return db().fetch_one(sql, {"wxOpenId": wx_open_id})

    def select_user_by_email(self, email: str) -> Optional[Dict]:
        sql = (
            "SELECT userId, username, wxOpenId, wxUnionId, `name`, tel, email, avatar, password, state, "
            "isAdmin, roleId, loginIp, loginTime, createTime FROM sys_user WHERE email = :email"
        )
        return db().fetch_one(sql, {"email": email})

    def select_user_by_tel(self, tel: str) -> Optional[Dict]:
        sql = (
            "SELECT userId, username, wxOpenId, wxUnionId, `name`, tel, email, avatar, password, state, "
            "isAdmin, roleId, loginIp, loginTime, createTime FROM sys_user WHERE tel = :tel"
        )
        return db().fetch_one(sql, {"tel": tel})

    def add(self, user: Dict) -> int:
        sql = (
            "INSERT INTO sys_user (username, `name`, tel, email, password, wxOpenId, state, roleId, isAdmin) "
            "VALUES (:username, :name, :tel, :email, :password, :wxOpenId, '1', :roleId, '0')"
        )
        return db().execute(
            sql,
            {
                "username": user.get("username"),
                "name": user.get("name"),
                "tel": user.get("tel"),
                "email": user.get("email"),
                "password": user.get("password"),
                "wxOpenId": user.get("wxOpenId"),
                "roleId": user.get("roleId", 2),
            },
        )

    def update(self, user: Dict) -> int:
        sets = []
        params = {}
        for key in ["name", "tel", "email", "password", "avatar", "roleId", "wxOpenId", "state"]:
            if user.get(key) not in (None, ""):
                sets.append(f"{key} = :{key}")
                params[key] = user.get(key)
        if not sets:
            return 0
        where = []
        if user.get("userId"):
            where.append("userId = :userId")
            params["userId"] = user.get("userId")
        elif user.get("username"):
            where.append("username = :username")
            params["username"] = user.get("username")
        else:
            return 0
        sql = f"UPDATE sys_user SET {', '.join(sets)} WHERE {' AND '.join(where)}"
        return db().execute(sql, params)

    def generate_code(self, email: str | None, tel: str | None, code: Optional[str] = None) -> str:
        code = code or f"{random.randint(0, 999999):06d}"
        sql = "INSERT INTO sys_code (email, code, createTime) VALUES (:email, :code, NOW())"
        db().execute(sql, {"email": email or tel, "code": code})
        return code

    def query_captcha(self, code: str, email_or_tel: str) -> int:
        sql = (
            "SELECT count(*) FROM sys_code WHERE code = :code AND email = :email "
            "AND createTime >= DATE_SUB(NOW(), INTERVAL 10 MINUTE) ORDER BY createTime DESC LIMIT 1"
        )
        value = db().fetch_value(sql, {"code": code, "email": email_or_tel})
        return int(value or 0)


__all__ = ["SysUserService"]
