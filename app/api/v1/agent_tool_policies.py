from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, Query, status

from app.api.deps import (
    get_create_agent_tool_policy,
    get_delete_agent_tool_policy,
    get_get_agent_tool_policy,
    get_list_agent_tool_policies,
    get_update_agent_tool_policy,
)
from app.api.schemas import (
    AgentToolPolicyCreate,
    AgentToolPolicyDeleteRequest,
    AgentToolPolicyResponse,
    AgentToolPolicyUpdate,
)
from app.application.agent_tool_policy.use_cases import (
    CreateAgentToolPolicyCommand,
    CreateAgentToolPolicyUseCase,
    DeleteAgentToolPolicyCommand,
    DeleteAgentToolPolicyUseCase,
    GetAgentToolPolicyUseCase,
    ListAgentToolPoliciesUseCase,
    UpdateAgentToolPolicyCommand,
    UpdateAgentToolPolicyUseCase,
)
from app.domain.agent_tool_policy.agent_tool_policy import AgentToolPolicy

router = APIRouter(prefix="/agent-tool-policies", tags=["Agent Tool Policies"])

_ACTOR_HEADER = "X-Acting-User"
_REASON_HEADER = "X-Change-Reason"


def _to_response(p: AgentToolPolicy) -> AgentToolPolicyResponse:
    return AgentToolPolicyResponse(
        policy_id=p.policy_id,
        agent_id=p.agent_id,
        tool_name=p.tool_name,
        policy_type=p.policy_type,
        enabled=p.enabled,
        reason=p.reason,
        created_by=p.created_by,
        created_at=p.created_at,
    )


@router.post("", response_model=AgentToolPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: AgentToolPolicyCreate,
    uc: CreateAgentToolPolicyUseCase = Depends(get_create_agent_tool_policy),
    x_acting_user: Optional[str] = Header(default=None, alias=_ACTOR_HEADER),
):
    created_by = body.created_by or x_acting_user or ""
    return _to_response(uc.execute(CreateAgentToolPolicyCommand(
        agent_id=body.agent_id,
        tool_name=body.tool_name,
        policy_type=body.policy_type,
        reason=body.reason,
        created_by=created_by,
    )))


@router.get("", response_model=List[AgentToolPolicyResponse])
def list_policies(
    agent_id: Optional[str] = Query(default=None),
    uc: ListAgentToolPoliciesUseCase = Depends(get_list_agent_tool_policies),
):
    return [_to_response(p) for p in uc.execute(agent_id=agent_id)]


@router.get("/{policy_id}", response_model=AgentToolPolicyResponse)
def get_policy(
    policy_id: str,
    uc: GetAgentToolPolicyUseCase = Depends(get_get_agent_tool_policy),
):
    return _to_response(uc.execute(policy_id))


@router.patch("/{policy_id}", response_model=AgentToolPolicyResponse)
def update_policy(
    policy_id: str,
    body: AgentToolPolicyUpdate,
    uc: UpdateAgentToolPolicyUseCase = Depends(get_update_agent_tool_policy),
    x_acting_user: Optional[str] = Header(default=None, alias=_ACTOR_HEADER),
    x_change_reason: Optional[str] = Header(default=None, alias=_REASON_HEADER),
):
    return _to_response(uc.execute(UpdateAgentToolPolicyCommand(
        policy_id=policy_id,
        enabled=body.enabled,
        reason=body.reason,
        changed_by=body.changed_by or x_acting_user or "",
        change_reason=body.change_reason or x_change_reason or "",
    )))


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: str,
    body: AgentToolPolicyDeleteRequest = Body(default=AgentToolPolicyDeleteRequest()),
    uc: DeleteAgentToolPolicyUseCase = Depends(get_delete_agent_tool_policy),
    x_acting_user: Optional[str] = Header(default=None, alias=_ACTOR_HEADER),
    x_change_reason: Optional[str] = Header(default=None, alias=_REASON_HEADER),
):
    uc.execute(DeleteAgentToolPolicyCommand(
        policy_id=policy_id,
        changed_by=body.changed_by or x_acting_user or "",
        change_reason=body.change_reason or x_change_reason or "",
    ))
