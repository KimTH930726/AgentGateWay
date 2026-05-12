from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_approve_tool_call, get_get_approval,
    get_list_approvals, get_reject_tool_call,
)
from app.api.schemas import ApprovalActionRequest, ApprovalResponse
from app.application.approval.use_cases import (
    ApproveCommand, ApproveToolCallUseCase, GetApprovalUseCase,
    ListApprovalsUseCase, RejectCommand, RejectToolCallUseCase,
)
from app.domain.shared.exceptions import DomainError, NotFoundError
from app.domain.tool_call.tool_call import ToolCall

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _to_response(tc: ToolCall) -> ApprovalResponse:
    a = tc.approval
    if a is None:
        raise ValueError(f"ToolCall {tc.request_id} has no approval record")
    return ApprovalResponse(
        approval_id=a.approval_id,
        request_id=tc.request_id,
        agent_id=tc.agent_id,
        user_id=tc.user_id,
        tool_name=tc.tool_name,
        risk_level=tc.risk_level,
        status=a.status,
        approver_id=a.approver_id,
        reason=a.reason,
        created_at=a.created_at,
        decided_at=a.decided_at,
    )


@router.get("", response_model=List[ApprovalResponse])
def list_approvals(
    pending_only: bool = Query(default=False),
    uc: ListApprovalsUseCase = Depends(get_list_approvals),
):
    return [_to_response(tc) for tc in uc.execute(pending_only=pending_only)]


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval(approval_id: str, uc: GetApprovalUseCase = Depends(get_get_approval)):
    try:
        return _to_response(uc.execute(approval_id))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve(
    approval_id: str,
    body: ApprovalActionRequest,
    uc: ApproveToolCallUseCase = Depends(get_approve_tool_call),
):
    try:
        return _to_response(uc.execute(ApproveCommand(
            approval_id=approval_id,
            approver_id=body.approver_id,
            reason=body.reason,
        )))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject(
    approval_id: str,
    body: ApprovalActionRequest,
    uc: RejectToolCallUseCase = Depends(get_reject_tool_call),
):
    try:
        return _to_response(uc.execute(RejectCommand(
            approval_id=approval_id,
            approver_id=body.approver_id,
            reason=body.reason,
        )))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
