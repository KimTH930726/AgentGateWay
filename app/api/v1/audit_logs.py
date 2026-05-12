from fastapi import APIRouter, Depends, Query

from app.api.deps import get_tool_call_repo
from app.api.schemas import AuditLogPage, AuditLogResponse
from app.domain.shared.exceptions import NotFoundError
from app.domain.tool_call.tool_call import ToolCall
from app.infrastructure.persistence.repositories.tool_call_repository import ToolCallRepository

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _to_response(tc: ToolCall) -> AuditLogResponse:
    return AuditLogResponse(
        request_id=tc.request_id,
        trace_id=tc.trace_id,
        agent_id=tc.agent_id,
        user_id=tc.user_id,
        tool_name=tc.tool_name,
        input_hash=tc.input_data.hash,
        risk_level=tc.risk_level,
        policy_decision=tc.policy_decision,
        policy_reason=tc.policy_reason,
        approval_status=tc.approval.status if tc.approval else None,
        execution_status=tc.execution_status,
        estimated_cost=tc.estimated_cost,
        actual_cost=tc.actual_cost,
        duration_ms=tc.duration_ms,
        created_at=tc.created_at,
        executed_at=tc.executed_at,
    )


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    repo: ToolCallRepository = Depends(get_tool_call_repo),
):
    items = [_to_response(tc) for tc in repo.find_all(limit=limit, offset=offset)]
    total = repo.count_all()
    return AuditLogPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_next=(offset + limit) < total,
    )


@router.get("/{request_id}", response_model=AuditLogResponse)
def get_audit_log(request_id: str, repo: ToolCallRepository = Depends(get_tool_call_repo)):
    tc = repo.find_by_request_id(request_id)
    if not tc:
        raise NotFoundError(f"Audit log not found: {request_id}")
    return _to_response(tc)
