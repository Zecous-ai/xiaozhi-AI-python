from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import ResultMessage
from app.services.agent_service import SysAgentService
from app.services.config_service import SysConfigService
from app.utils.request_utils import parse_body


router = APIRouter()
agent_service = SysAgentService(SysConfigService())


@router.get("")
async def list_agents(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    agent = {
        "provider": params.get("provider"),
        "agentName": params.get("agentName"),
        "userId": user.get("userId"),
    }
    agents = agent_service.query(agent)
    return ResultMessage.success(data={"list": agents, "total": len(agents)})


@router.post("")
async def create_agent(request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["userId"] = user.get("userId")
    return ResultMessage.success(data)


@router.put("/{agent_id}")
async def update_agent(agent_id: int, request: Request, user=Depends(get_current_user)):
    data = await parse_body(request)
    data["agentId"] = agent_id
    data["userId"] = user.get("userId")
    return ResultMessage.success("更新成功")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, user=Depends(get_current_user)):
    return ResultMessage.success("删除成功")

