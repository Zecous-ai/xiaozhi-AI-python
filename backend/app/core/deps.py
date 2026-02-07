from __future__ import annotations

from fastapi import Header, HTTPException, Request

from app.core.response import ResultMessage, ResultStatus
from app.core.security import parse_bearer_token, token_manager
from app.services.user_service import SysUserService


user_service = SysUserService()


async def get_current_user(request: Request, authorization: str | None = Header(default=None)) -> dict:
    token = parse_bearer_token(authorization)
    user_id = token_manager().get_user_id(token or "")
    if not user_id:
        raise HTTPException(status_code=ResultStatus.UNAUTHORIZED, detail="未授权")
    user = user_service.select_user_by_user_id(user_id)
    if not user:
        raise HTTPException(status_code=ResultStatus.UNAUTHORIZED, detail="用户不存在")
    request.state.user = user
    return user


__all__ = ["get_current_user"]
