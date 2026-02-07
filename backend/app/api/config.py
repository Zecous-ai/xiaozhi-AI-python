from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import ResultMessage
from app.services.config_service import SysConfigService
from app.utils.dto import config_to_dto
from app.utils.pagination import build_page
from app.utils.request_utils import parse_body


router = APIRouter()
config_service = SysConfigService()


@router.get("")
async def list_configs(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    page_num = int(params.get("start", 1))
    page_size = int(params.get("limit", 10))
    filters = {
        "userId": user.get("userId"),
        "configType": params.get("configType"),
        "modelType": params.get("modelType"),
        "provider": params.get("provider"),
        "configName": params.get("configName"),
        "isDefault": params.get("isDefault"),
    }
    configs = config_service.query(filters)
    total = len(configs)
    start_idx = (page_num - 1) * page_size
    page_items = configs[start_idx : start_idx + page_size]
    page = build_page([config_to_dto(c) for c in page_items], total, page_num, page_size)
    return ResultMessage.success(data=page)


@router.post("")
async def create_config(request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["userId"] = user.get("userId")
    if data.get("isDefault") == "1":
        config_service.reset_default(data.get("configType"), user.get("userId"), data.get("modelType"))
    config_service.add(data)
    return ResultMessage.success(config_to_dto(data))


@router.put("/{config_id}")
async def update_config(config_id: int, request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["configId"] = config_id
    data["userId"] = user.get("userId")
    if data.get("isDefault") == "1":
        config_service.reset_default(data.get("configType"), user.get("userId"), data.get("modelType"))
    config_service.update(data)
    updated = config_service.select_config_by_id(config_id)
    return ResultMessage.success(config_to_dto(updated))


@router.post("/getModels")
async def get_models(request: Request):
    data = await parse_body(request)
    api_url = data.get("apiUrl")
    api_key = data.get("apiKey")
    if not api_url or not api_key:
        return ResultMessage.error("参数错误")
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = httpx.get(f"{api_url}/models", headers=headers, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        model_list = payload.get("data") or []
        result = ResultMessage.success()
        result["data"] = model_list
        return result
    except Exception as exc:
        return ResultMessage.error(f"调用模型接口失败: {exc}")

