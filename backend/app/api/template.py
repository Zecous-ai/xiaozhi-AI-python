from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import ResultMessage
from app.services.template_service import SysTemplateService
from app.utils.request_utils import parse_body


router = APIRouter()
template_service = SysTemplateService()


@router.get("")
async def list_templates(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    templates = template_service.query(
        user.get("userId"), params.get("templateName"), params.get("category")
    )
    result = ResultMessage.success()
    result["data"] = {"list": templates, "total": len(templates)}
    return result


@router.post("")
async def create_template(request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["userId"] = user.get("userId")
    template_service.add(data)
    return ResultMessage.success(data)


@router.put("/{template_id}")
async def update_template(template_id: int, request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["templateId"] = template_id
    data["userId"] = user.get("userId")
    template_service.update(data)
    updated = template_service.select_by_id(template_id)
    return ResultMessage.success(updated)


@router.delete("/{template_id}")
async def delete_template(template_id: int, user=Depends(get_current_user)):
    template_service.delete(template_id)
    return ResultMessage.success("删除成功")

