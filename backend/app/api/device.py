from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request, Response

from app.core.deps import get_current_user
from app.core.response import ResultMessage
from app.services.device_service import SysDeviceService
from app.services.role_service import SysRoleService
from app.utils.cms_utils import get_ota_address, get_websocket_address
from app.utils.dto import device_to_dto
from app.utils.mac_utils import is_mac_address_valid
from app.utils.request_utils import parse_body


router = APIRouter()
device_service = SysDeviceService()
role_service = SysRoleService()


@router.get("")
async def query_devices(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    page_num = int(params.get("start", 1))
    page_size = int(params.get("limit", 10))
    filters = {
        "userId": user.get("userId"),
        "deviceId": params.get("deviceId"),
        "deviceName": params.get("deviceName"),
        "roleName": params.get("roleName"),
        "state": params.get("state"),
        "roleId": params.get("roleId"),
    }
    page = device_service.query(filters, page_num, page_size)
    return ResultMessage.success(data=page)


@router.post("/batchUpdate")
async def batch_update(request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    device_ids = (data.get("deviceIds") or "").split(",")
    device_ids = [device_id.strip() for device_id in device_ids if device_id.strip()]
    if not device_ids:
        return ResultMessage.error("设备ID格式不正确")
    role_id = data.get("roleId")
    success = device_service.batch_update(device_ids, user.get("userId"), int(role_id) if role_id else None)
    if success > 0:
        result = ResultMessage.success(f"成功更新{success}个设备")
        result["successCount"] = success
        result["totalCount"] = len(device_ids)
        return result
    return ResultMessage.error("更新失败，请检查设备ID是否正确")


@router.post("")
async def create_device(request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    code = data.get("code")
    query = device_service.query_verify_code(code=code) if code else None
    if not query:
        return ResultMessage.error("无效验证码")
    roles = role_service.query({"userId": user.get("userId")})
    if not roles:
        return ResultMessage.error("没有配置角色")
    selected_role = None
    for role in roles:
        if role.get("isDefault") == "1":
            selected_role = role
            break
    if not selected_role:
        selected_role = roles[0]

    device = {
        "code": code,
        "userId": user.get("userId"),
        "deviceName": query.get("type") or "小智",
        "type": query.get("type"),
        "deviceId": query.get("deviceId"),
        "roleId": selected_role.get("roleId"),
    }
    device_service.add(device)
    added = device_service.select_device_by_id(device.get("deviceId"))
    return ResultMessage.success(device_to_dto(added))


@router.put("/{device_id}")
async def update_device(device_id: str, request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    device = {**data, "deviceId": device_id, "userId": user.get("userId")}
    device_service.update(device)
    updated = device_service.select_device_by_id(device_id)
    return ResultMessage.success(device_to_dto(updated))


@router.delete("/{device_id}")
async def delete_device(device_id: str, user=Depends(get_current_user)):
    rows = device_service.delete(device_id, user.get("userId"))
    if rows > 0:
        device_service.delete_messages_for_device(device_id, user.get("userId"))
        return ResultMessage.success("删除成功")
    return ResultMessage.error("删除失败")


@router.get("/export")
async def export_devices(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    filters = {
        "userId": user.get("userId"),
        "deviceId": params.get("deviceId"),
        "deviceName": params.get("deviceName"),
        "roleName": params.get("roleName"),
        "state": params.get("state"),
        "roleId": params.get("roleId"),
    }
    devices = device_service.query_all(filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "deviceId",
            "deviceName",
            "type",
            "state",
            "roleName",
            "lastLogin",
            "createTime",
            "ip",
            "wifiName",
            "chipModelName",
            "version",
            "totalMessage",
        ]
    )
    for item in devices:
        writer.writerow(
            [
                item.get("deviceId") or "",
                item.get("deviceName") or "",
                item.get("type") or "",
                item.get("state") or "",
                item.get("roleName") or "",
                item.get("lastLogin") or "",
                item.get("createTime") or "",
                item.get("ip") or "",
                item.get("wifiName") or "",
                item.get("chipModelName") or "",
                item.get("version") or "",
                item.get("totalMessage") or 0,
            ]
        )

    filename = f"device_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content="﻿" + output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)


@router.post("/ota")
async def ota(
    request: Request,
    device_id: str | None = Header(default=None, alias="Device-Id"),
):
    body = await request.body()
    data = {}
    if body:
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}

    device_id = device_id or data.get("mac_address") or data.get("mac")
    if not is_mac_address_valid(device_id):
        error_msg = "设备ID不正确"
        return Response(content=json.dumps({"error": error_msg}, ensure_ascii=False), media_type="application/json", status_code=400)

    device = {
        "deviceId": device_id,
        "lastLogin": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "wifiName": data.get("board", {}).get("ssid") if isinstance(data.get("board"), dict) else None,
        "type": data.get("board", {}).get("type") if isinstance(data.get("board"), dict) else None,
        "chipModelName": data.get("chip_model_name"),
        "version": (data.get("application") or {}).get("version") if isinstance(data.get("application"), dict) else None,
        "ip": request.client.host if request.client else None,
    }

    existing = device_service.query({"deviceId": device_id}, 1, 1)
    response_data = {}
    if not existing.get("list"):
        code_result = device_service.generate_code(device_id, None, device.get("type"))
        response_data["activation"] = {
            "code": code_result.get("code"),
            "message": code_result.get("code"),
            "challenge": device_id,
        }
    else:
        device_service.update(device)
        response_data["websocket"] = {"url": get_websocket_address(), "token": ""}

    response_data["firmware"] = {"url": get_ota_address(), "version": "1.0.0"}
    response_data["server_time"] = {"timestamp": int(datetime.utcnow().timestamp() * 1000), "timezone_offset": 480}

    return Response(content=json.dumps(response_data, ensure_ascii=False), media_type="application/json")


@router.post("/ota/activate")
async def ota_activate(device_id: str | None = Header(default=None, alias="Device-Id")):
    if not is_mac_address_valid(device_id):
        return Response(status_code=202)
    device = device_service.select_device_by_id(device_id)
    if not device:
        return Response(status_code=202)
    return Response(content="success", media_type="text/plain")
