from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_tool_call_repo
from app.api.schemas import AuditLogResponse
from app.domain.tool_call.tool_call import ToolCall
from app.infrastructure.persistence.repositories.tool_call_repository import ToolCallRepository

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _to_response(tc: ToolCall) -> AuditLogResponse:
    return AuditLogResponse(
        request_id=tc.request_id,
        agent_id=tc.agent_id,
        user_id=tc.user_id,
        tool_name=tc.tool_name,
        input_hash=tc.input_data.hash,
        risk_level=tc.risk_level,
        policy_decision=tc.policy_decision,
        approval_status=tc.approval.status if tc.approval else None,
        execution_status=tc.execution_status,
        estimated_cost=tc.estimated_cost,
        actual_cost=tc.actual_cost,
        created_at=tc.created_at,
        executed_at=tc.executed_at,
    )


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    repo: ToolCallRepository = Depends(get_tool_call_repo),
):
    return [_to_response(tc) for tc in repo.find_all(limit=limit, offset=offset)]


@router.get("/{request_id}", response_model=AuditLogResponse)
def get_audit_log(request_id: str, repo: ToolCallRepository = Depends(get_tool_call_repo)):
    tc = repo.find_by_request_id(request_id)
    if not tc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return _to_response(tc)
