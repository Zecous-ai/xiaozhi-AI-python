from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response

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
        "roleId": params.get("roleId"),
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
async def export_messages(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    filters = {
        "userId": user.get("userId"),
        "deviceId": params.get("deviceId"),
        "roleId": params.get("roleId"),
        "messageType": params.get("messageType"),
        "deviceName": params.get("deviceName"),
        "sender": params.get("sender"),
        "startTime": params.get("startTime"),
        "endTime": params.get("endTime"),
    }
    messages = message_service.query_all(filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "messageId",
            "deviceId",
            "deviceName",
            "roleId",
            "roleName",
            "sender",
            "messageType",
            "message",
            "createTime",
        ]
    )
    for item in messages:
        writer.writerow(
            [
                item.get("messageId") or "",
                item.get("deviceId") or "",
                item.get("deviceName") or "",
                item.get("roleId") or "",
                item.get("roleName") or "",
                item.get("sender") or "",
                item.get("messageType") or "",
                item.get("message") or "",
                item.get("createTime") or "",
            ]
        )

    filename = f"message_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content="﻿" + output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
