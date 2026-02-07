from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import ResultMessage
from app.services.sys_message_service import SysMessageService


router = APIRouter()
message_service = SysMessageService()


@router.get("")
async def list_messages(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    page_num = int(params.get("start", 1))
    page_size = int(params.get("limit", 10))
    filters = {
        "userId": user.get("userId"),
        "deviceId": params.get("deviceId"),
        "messageType": params.get("messageType"),
        "deviceName": params.get("deviceName"),
        "sender": params.get("sender"),
        "startTime": params.get("startTime"),
        "endTime": params.get("endTime"),
    }
    page = message_service.query(filters, page_num, page_size)
    return ResultMessage.success(data=page)


@router.delete("/{message_id}")
async def delete_message(message_id: int, user=Depends(get_current_user)):
    message_service.delete(user.get("userId"), message_id=message_id)
    return ResultMessage.success("删除成功")


@router.delete("")
async def delete_messages(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    device_id = params.get("deviceId")
    message_service.delete(user.get("userId"), device_id=device_id)
    return ResultMessage.success("删除成功")


@router.get("/export")
async def export_messages(user=Depends(get_current_user)):
    return ResultMessage.error("未实现")
