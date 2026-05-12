"""
Unit tests for the ToolCall aggregate root.
No DB, no HTTP — pure domain logic.
"""
import pytest

from app.domain.enums import ApprovalStatus, ExecutionStatus, PolicyDecision, RiskLevel
from app.domain.shared.exceptions import DomainError
from app.domain.shared.value_objects import ExecutionResult, InputData
from app.domain.tool_call.tool_call import ToolCall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allow_call() -> ToolCall:
    return ToolCall.create(
        agent_id="agent-1",
        user_id="user-1",
        tool_name="get_order_detail",
        input_data=InputData(payload={"order_id": "ORD-1"}),
        risk_level=RiskLevel.LOW,
        policy_decision=PolicyDecision.ALLOW,
    )


def _approval_required_call() -> ToolCall:
    return ToolCall.create(
        agent_id="agent-1",
        user_id="user-1",
        tool_name="refund_order",
        input_data=InputData(payload={"order_id": "ORD-1", "amount": 5000}),
        risk_level=RiskLevel.HIGH,
        policy_decision=PolicyDecision.REQUIRE_APPROVAL,
    )


def _deny_call() -> ToolCall:
    return ToolCall.create(
        agent_id="agent-1",
        user_id="user-1",
        tool_name="refund_order",
        input_data=InputData(payload={}),
        risk_level=RiskLevel.HIGH,
        policy_decision=PolicyDecision.DENY,
    )


def _ok_result() -> ExecutionResult:
    return ExecutionResult(status=ExecutionStatus.SIMULATED, output={}, cost=0.01)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def test_create_generates_unique_request_ids():
    a = _allow_call()
    b = _allow_call()
    assert a.request_id != b.request_id


def test_create_sets_correct_fields():
    tc = _allow_call()
    assert tc.tool_name == "get_order_detail"
    assert tc.risk_level == RiskLevel.LOW
    assert tc.policy_decision == PolicyDecision.ALLOW
    assert tc.approval is None
    assert tc.execution_status is None


# ---------------------------------------------------------------------------
# deny()
# ---------------------------------------------------------------------------

def test_deny_sets_skipped_status():
    tc = _deny_call()
    tc.deny("insufficient role")
    assert tc.execution_status == ExecutionStatus.SKIPPED
    assert tc.error_message == "insufficient role"


def test_deny_on_allow_decision_raises():
    tc = _allow_call()
    with pytest.raises(DomainError):
        tc.deny("nope")


def test_deny_on_require_approval_decision_raises():
    tc = _approval_required_call()
    with pytest.raises(DomainError):
        tc.deny("nope")


# ---------------------------------------------------------------------------
# request_approval()
# ---------------------------------------------------------------------------

def test_request_approval_creates_pending_approval():
    tc = _approval_required_call()
    tc.request_approval()
    assert tc.approval is not None
    assert tc.approval.status == ApprovalStatus.PENDING
    assert tc.approval.approval_id  # non-empty UUID string


def test_request_approval_twice_raises():
    tc = _approval_required_call()
    tc.request_approval()
    with pytest.raises(DomainError):
        tc.request_approval()


def test_request_approval_on_allow_decision_raises():
    tc = _allow_call()
    with pytest.raises(DomainError):
        tc.request_approval()


# ---------------------------------------------------------------------------
# approve()
# ---------------------------------------------------------------------------

def test_approve_changes_status():
    tc = _approval_required_call()
    tc.request_approval()
    tc.approve("admin-1", "looks good")
    assert tc.approval.status == ApprovalStatus.APPROVED
    assert tc.approval.approver_id == "admin-1"
    assert tc.approval.decided_at is not None


def test_approve_without_approval_raises():
    tc = _approval_required_call()
    with pytest.raises(DomainError):
        tc.approve("admin-1")


def test_approve_already_approved_raises():
    tc = _approval_required_call()
    tc.request_approval()
    tc.approve("admin-1")
    with pytest.raises(DomainError):
        tc.approve("admin-2")


# ---------------------------------------------------------------------------
# reject()
# ---------------------------------------------------------------------------

def test_reject_changes_status():
    tc = _approval_required_call()
    tc.request_approval()
    tc.reject("admin-1", "fraud risk")
    assert tc.approval.status == ApprovalStatus.REJECTED
    assert tc.approval.reason == "fraud risk"


def test_reject_after_approve_raises():
    tc = _approval_required_call()
    tc.request_approval()
    tc.approve("admin-1")
    with pytest.raises(DomainError):
        tc.reject("admin-1")


# ---------------------------------------------------------------------------
# record_execution()
# ---------------------------------------------------------------------------

def test_record_execution_direct_allow():
    tc = _allow_call()
    tc.record_execution(_ok_result())
    assert tc.execution_status == ExecutionStatus.SIMULATED
    assert tc.actual_cost == 0.01
    assert tc.executed_at is not None


def test_record_execution_after_approval():
    tc = _approval_required_call()
    tc.request_approval()
    tc.approve("admin-1")
    tc.record_execution(_ok_result())
    assert tc.execution_status == ExecutionStatus.SIMULATED


def test_record_execution_requires_approval_when_policy_says_so():
    tc = _approval_required_call()
    tc.request_approval()
    # not yet approved
    with pytest.raises(DomainError):
        tc.record_execution(_ok_result())


def test_record_execution_on_rejected_call_raises():
    tc = _approval_required_call()
    tc.request_approval()
    tc.reject("admin-1", "no")
    with pytest.raises(DomainError):
        tc.record_execution(_ok_result())
