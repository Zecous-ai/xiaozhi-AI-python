from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import ResultMessage
from app.dialogue.tts_service import EdgeTtsService
from app.services.role_service import SysRoleService
from app.utils.request_utils import parse_body


router = APIRouter()
role_service = SysRoleService()


@router.get("")
async def list_roles(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    page_num = int(params.get("start", 1))
    page_size = int(params.get("limit", 10))
    filters = {
        "userId": user.get("userId"),
        "roleId": params.get("roleId"),
        "roleName": params.get("roleName"),
        "isDefault": params.get("isDefault"),
    }
    page = role_service.query(filters, page_num, page_size)
    return ResultMessage.success(data=page)


@router.post("")
async def create_role(request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["userId"] = user.get("userId")
    role_service.add(data)
    return ResultMessage.success(data)


@router.put("/{role_id}")
async def update_role(role_id: int, request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["roleId"] = role_id
    data["userId"] = user.get("userId")
    role_service.update(data)
    updated = role_service.select_role_by_id(role_id)
    return ResultMessage.success(updated)


@router.delete("/{role_id}")
async def delete_role(role_id: int, user=Depends(get_current_user)):
    role = role_service.select_role_by_id(role_id)
    if not role:
        return ResultMessage.error("角色不存在")
    if role.get("userId") != user.get("userId"):
        return ResultMessage.error("无权删除该角色")
    role_service.delete(role_id)
    return ResultMessage.success("删除成功")


@router.get("/testVoice")
async def test_voice(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    provider = params.get("provider")
    voice_name = params.get("voiceName") or "zh-CN-XiaoxiaoNeural"
    message = params.get("message") or "语音合成测试"
    tts_pitch = float(params.get("ttsPitch") or 1.0)
    tts_speed = float(params.get("ttsSpeed") or 1.0)
    if provider == "edge":
        service = EdgeTtsService(voice_name, tts_pitch, tts_speed)
        audio_path = await service.text_to_speech(message)
        result = ResultMessage.success()
        result["data"] = audio_path
        return result
    return ResultMessage.error("暂不支持该语音服务商")
