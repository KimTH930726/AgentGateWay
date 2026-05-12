from fastapi import APIRouter, Depends, Request

from app.api.deps import get_execute_approved, get_invoke_tool
from app.api.schemas import InvokeRequest, InvokeResponse
from app.application.gateway.use_cases import ExecuteApprovedUseCase, InvokeToolCommand, InvokeToolUseCase
from app.domain.tool_call.tool_call import ToolCall

router = APIRouter(prefix="/gateway", tags=["Gateway"])

_TRACE_HEADER = "X-Trace-Id"


def _to_response(tc: ToolCall) -> InvokeResponse:
    return InvokeResponse(
        request_id=tc.request_id,
        tool_name=tc.tool_name,
        policy_decision=tc.policy_decision,
        policy_reason=tc.policy_reason,
        trace_id=tc.trace_id,
        approval_status=tc.approval.status if tc.approval else None,
        execution_status=tc.execution_status,
        risk_level=tc.risk_level,
        estimated_cost=tc.estimated_cost,
        actual_cost=tc.actual_cost,
        duration_ms=tc.duration_ms,
        error_message=tc.error_message,
        created_at=tc.created_at,
        executed_at=tc.executed_at,
    )


@router.post("/invoke", response_model=InvokeResponse)
def invoke_tool(
    body: InvokeRequest,
    request: Request,
    uc: InvokeToolUseCase = Depends(get_invoke_tool),
):
    trace_id = body.trace_id or request.headers.get(_TRACE_HEADER, "")
    result = uc.execute(InvokeToolCommand(
        agent_id=body.agent_id,
        user_id=body.user_id,
        tool_name=body.tool_name,
        input_data=body.input,
        trace_id=trace_id,
    ))
    return _to_response(result)


@router.post("/execute/{request_id}", response_model=InvokeResponse)
def execute_approved(
    request_id: str,
    uc: ExecuteApprovedUseCase = Depends(get_execute_approved),
):
    result = uc.execute(request_id)
    return _to_response(result)
