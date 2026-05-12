"""
ToolCall — Aggregate Root
Owns the complete lifecycle of a single tool invocation:
  create → (deny | request_approval → approve/reject → execute | execute directly)
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.domain.enums import ApprovalStatus, ExecutionStatus, PolicyDecision, RiskLevel
from app.domain.shared.exceptions import DomainError
from app.domain.shared.value_objects import ExecutionResult, InputData


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Approval — Entity contained by the ToolCall aggregate
# ---------------------------------------------------------------------------

@dataclass
class Approval:
    approval_id: str
    status: ApprovalStatus
    approver_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=_now)
    decided_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# ToolCall — Aggregate Root
# ---------------------------------------------------------------------------

class ToolCall:

    def __init__(
        self,
        request_id: str,
        agent_id: str,
        user_id: str,
        tool_name: str,
        input_data: InputData,
        risk_level: RiskLevel,
        policy_decision: PolicyDecision,
        estimated_cost: float,
        created_at: datetime,
        approval: Optional[Approval] = None,
        execution_status: Optional[ExecutionStatus] = None,
        actual_cost: Optional[float] = None,
        error_message: Optional[str] = None,
        executed_at: Optional[datetime] = None,
    ) -> None:
        self._request_id = request_id
        self._agent_id = agent_id
        self._user_id = user_id
        self._tool_name = tool_name
        self._input_data = input_data
        self._risk_level = risk_level
        self._policy_decision = policy_decision
        self._estimated_cost = estimated_cost
        self._created_at = created_at
        self._approval = approval
        self._execution_status = execution_status
        self._actual_cost = actual_cost
        self._error_message = error_message
        self._executed_at = executed_at

    # --- Factory -----------------------------------------------------------

    @classmethod
    def create(
        cls,
        agent_id: str,
        user_id: str,
        tool_name: str,
        input_data: InputData,
        risk_level: RiskLevel,
        policy_decision: PolicyDecision,
        estimated_cost: float = 0.01,
    ) -> "ToolCall":
        return cls(
            request_id=str(uuid.uuid4()),
            agent_id=agent_id,
            user_id=user_id,
            tool_name=tool_name,
            input_data=input_data,
            risk_level=risk_level,
            policy_decision=policy_decision,
            estimated_cost=estimated_cost,
            created_at=_now(),
        )

    # --- State-machine commands --------------------------------------------

    def deny(self, reason: str) -> None:
        """Called immediately when policy decision is DENY."""
        if self._policy_decision != PolicyDecision.DENY:
            raise DomainError("Cannot deny: policy decision is not DENY")
        self._execution_status = ExecutionStatus.SKIPPED
        self._error_message = reason

    def request_approval(self) -> None:
        """Opens an approval gate; creates the embedded Approval entity."""
        if self._policy_decision != PolicyDecision.REQUIRE_APPROVAL:
            raise DomainError("Cannot request approval: policy decision is not REQUIRE_APPROVAL")
        if self._approval is not None:
            raise DomainError("Approval already exists for this tool call")
        self._approval = Approval(
            approval_id=str(uuid.uuid4()),
            status=ApprovalStatus.PENDING,
        )

    def approve(self, approver_id: str, reason: Optional[str] = None) -> None:
        """Admin approves the pending request."""
        self._assert_approval_is(ApprovalStatus.PENDING)
        self._approval.status = ApprovalStatus.APPROVED
        self._approval.approver_id = approver_id
        self._approval.reason = reason
        self._approval.decided_at = _now()

    def reject(self, approver_id: str, reason: Optional[str] = None) -> None:
        """Admin rejects the pending request."""
        self._assert_approval_is(ApprovalStatus.PENDING)
        self._approval.status = ApprovalStatus.REJECTED
        self._approval.approver_id = approver_id
        self._approval.reason = reason
        self._approval.decided_at = _now()

    def record_execution(self, result: ExecutionResult) -> None:
        """Records the executor outcome; enforces approval pre-condition."""
        if self._policy_decision == PolicyDecision.REQUIRE_APPROVAL:
            self._assert_approval_is(ApprovalStatus.APPROVED)
        self._execution_status = result.status
        self._actual_cost = result.cost
        self._executed_at = _now()

    # --- Guards ------------------------------------------------------------

    def _assert_approval_is(self, expected: ApprovalStatus) -> None:
        if self._approval is None:
            raise DomainError("No approval record attached to this tool call")
        if self._approval.status != expected:
            raise DomainError(
                f"Expected approval status {expected}, got {self._approval.status}"
            )

    # --- Properties (read-only projection) ---------------------------------

    @property
    def request_id(self) -> str:
        return self._request_id

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def input_data(self) -> InputData:
        return self._input_data

    @property
    def risk_level(self) -> RiskLevel:
        return self._risk_level

    @property
    def policy_decision(self) -> PolicyDecision:
        return self._policy_decision

    @property
    def estimated_cost(self) -> float:
        return self._estimated_cost

    @property
    def actual_cost(self) -> Optional[float]:
        return self._actual_cost

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @property
    def execution_status(self) -> Optional[ExecutionStatus]:
        return self._execution_status

    @property
    def approval(self) -> Optional[Approval]:
        return self._approval

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def executed_at(self) -> Optional[datetime]:
        return self._executed_at
