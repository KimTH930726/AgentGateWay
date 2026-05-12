import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.enums import ApprovalStatus, ExecutionStatus, PolicyDecision, RiskLevel
from app.domain.shared.value_objects import InputData
from app.domain.tool_call.repository import IToolCallRepository
from app.domain.tool_call.tool_call import Approval, ToolCall
from app.infrastructure.persistence.orm_models import ApprovalORM, ToolCallORM


class ToolCallRepository(IToolCallRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    # --- Mapping -----------------------------------------------------------

    def _to_domain(self, row: ToolCallORM) -> ToolCall:
        approval = None
        if row.approval:
            a = row.approval
            approval = Approval(
                approval_id=str(a.id),
                status=ApprovalStatus(a.status),
                approver_id=a.approver_id,
                reason=a.reason,
                created_at=a.created_at,
                decided_at=a.updated_at if a.approver_id else None,
            )

        return ToolCall(
            request_id=row.request_id,
            agent_id=row.agent_id,
            user_id=row.user_id,
            tool_name=row.tool_name,
            input_data=InputData(payload=row.input_data),
            risk_level=RiskLevel(row.risk_level),
            policy_decision=PolicyDecision(row.policy_decision),
            estimated_cost=row.estimated_cost,
            created_at=row.created_at,
            trace_id=row.trace_id or "",
            policy_reason=row.policy_reason or "",
            duration_ms=row.duration_ms,
            approval=approval,
            execution_status=ExecutionStatus(row.execution_status) if row.execution_status else None,
            actual_cost=row.actual_cost,
            error_message=row.error_message,
            executed_at=row.executed_at,
        )

    # --- IToolCallRepository -----------------------------------------------

    def save(self, tool_call: ToolCall) -> None:
        tc_row = (
            self._db.query(ToolCallORM)
            .filter(ToolCallORM.request_id == tool_call.request_id)
            .first()
        )

        if tc_row is None:
            tc_row = ToolCallORM(
                id=uuid.uuid4(),
                request_id=tool_call.request_id,
                agent_id=tool_call.agent_id,
                user_id=tool_call.user_id,
                tool_name=tool_call.tool_name,
                input_data=tool_call.input_data.payload,
                input_hash=tool_call.input_data.hash,
                risk_level=tool_call.risk_level,
                policy_decision=tool_call.policy_decision,
                approval_status=tool_call.approval.status if tool_call.approval else None,
                execution_status=tool_call.execution_status,
                estimated_cost=tool_call.estimated_cost,
                actual_cost=tool_call.actual_cost,
                error_message=tool_call.error_message,
                trace_id=tool_call.trace_id,
                policy_reason=tool_call.policy_reason,
                duration_ms=tool_call.duration_ms,
                created_at=tool_call.created_at,
                executed_at=tool_call.executed_at,
            )
            self._db.add(tc_row)
            self._db.flush()
        else:
            tc_row.approval_status = tool_call.approval.status if tool_call.approval else None
            tc_row.execution_status = tool_call.execution_status
            tc_row.actual_cost = tool_call.actual_cost
            tc_row.error_message = tool_call.error_message
            tc_row.duration_ms = tool_call.duration_ms
            tc_row.executed_at = tool_call.executed_at

        if tool_call.approval:
            self._upsert_approval(tc_row.id, tool_call.approval)

        self._db.commit()

    def _upsert_approval(self, tool_call_pk: uuid.UUID, approval: Approval) -> None:
        aid = uuid.UUID(approval.approval_id)  # raises ValueError for malformed IDs — intentional

        a_row = self._db.query(ApprovalORM).filter(ApprovalORM.id == aid).first()
        now = datetime.now(timezone.utc)

        if a_row is None:
            a_row = ApprovalORM(
                id=aid,
                tool_call_id=tool_call_pk,
                status=approval.status,
                approver_id=approval.approver_id,
                reason=approval.reason,
                created_at=approval.created_at,
                updated_at=approval.decided_at or approval.created_at,
            )
            self._db.add(a_row)
        else:
            a_row.status = approval.status
            a_row.approver_id = approval.approver_id
            a_row.reason = approval.reason
            a_row.updated_at = approval.decided_at or now

    def find_by_request_id(self, request_id: str) -> Optional[ToolCall]:
        row = (
            self._db.query(ToolCallORM)
            .filter(ToolCallORM.request_id == request_id)
            .first()
        )
        return self._to_domain(row) if row else None

    def find_by_approval_id(self, approval_id: str) -> Optional[ToolCall]:
        try:
            aid = uuid.UUID(approval_id)
        except (ValueError, AttributeError):
            return None
        a_row = self._db.query(ApprovalORM).filter(ApprovalORM.id == aid).first()
        if not a_row:
            return None
        return self._to_domain(a_row.tool_call)

    def find_all(self, limit: int = 50, offset: int = 0) -> List[ToolCall]:
        rows = (
            self._db.query(ToolCallORM)
            .order_by(ToolCallORM.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def find_with_approvals(self, pending_only: bool = False) -> List[ToolCall]:
        q = self._db.query(ToolCallORM).join(ApprovalORM)
        if pending_only:
            q = q.filter(ApprovalORM.status == ApprovalStatus.PENDING)
        return [self._to_domain(r) for r in q.order_by(ToolCallORM.created_at.desc()).all()]

    def get_daily_cost(self, tool_name: str) -> float:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = (
            self._db.query(func.coalesce(func.sum(ToolCallORM.actual_cost), 0.0))
            .filter(ToolCallORM.tool_name == tool_name, ToolCallORM.created_at >= today)
            .scalar()
        )
        return float(result)

    def count_all(self) -> int:
        return self._db.query(func.count(ToolCallORM.id)).scalar() or 0
