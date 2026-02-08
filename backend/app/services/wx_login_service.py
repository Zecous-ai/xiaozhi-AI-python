from __future__ import annotations

from typing import Dict

import httpx

from app.core.config import settings


class WxLoginService:
    WX_LOGIN_URL = "https://api.weixin.qq.com/sns/jscode2session"

    async def get_wx_login_info(self, code: str) -> Dict[str, str]:
        appid = settings.wechat_appid
        secret = settings.wechat_secret
        if not appid or not secret:
            raise ValueError("微信登录未配置")

        params = {
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.WX_LOGIN_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"调用微信接口失败: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("微信接口返回格式错误")

        if payload.get("errcode"):
            errcode = payload.get("errcode")
            errmsg = payload.get("errmsg") or "unknown error"
            raise ValueError(f"微信登录失败: {errcode} {errmsg}")

        openid = payload.get("openid")
        if not openid:
            raise ValueError("获取微信openid失败")

        result: Dict[str, str] = {
            "openid": str(openid),
            "session_key": str(payload.get("session_key") or ""),
        }
        if payload.get("unionid"):
            result["unionid"] = str(payload["unionid"])
        return result


__all__ = ["WxLoginService"]
