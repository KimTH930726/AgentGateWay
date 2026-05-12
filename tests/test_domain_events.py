"""Unit tests for domain event emission from the ToolCall aggregate."""
import pytest

from app.domain.enums import ExecutionStatus, PolicyDecision, RiskLevel
from app.domain.shared.value_objects import ExecutionResult, InputData
from app.domain.tool_call.events import (
    ApprovalRequestedEvent,
    ToolCallApprovedEvent,
    ToolCallCreatedEvent,
    ToolCallDeniedEvent,
    ToolCallExecutedEvent,
    ToolCallRejectedEvent,
)
from app.domain.tool_call.tool_call import ToolCall


def _allow_call() -> ToolCall:
    return ToolCall.create(
        agent_id="agent-1",
        user_id="user-1",
        tool_name="get_order_detail",
        input_data=InputData(payload={"order_id": "ORD-1"}),
        risk_level=RiskLevel.LOW,
        policy_decision=PolicyDecision.ALLOW,
    )


def _approval_call() -> ToolCall:
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
    return ExecutionResult(status=ExecutionStatus.SIMULATED, output={}, cost=0.01, duration_ms=12)


class TestDomainEventEmission:
    def test_create_emits_created_event(self):
        tc = _allow_call()
        events = tc.collect_events()
        assert len(events) == 1
        e = events[0]
        assert isinstance(e, ToolCallCreatedEvent)
        assert e.tool_name == "get_order_detail"
        assert e.agent_id == "agent-1"
        assert e.request_id == tc.request_id

    def test_collect_clears_event_queue(self):
        tc = _allow_call()
        tc.collect_events()
        assert tc.collect_events() == []

    def test_deny_emits_denied_event(self):
        tc = _deny_call()
        tc.collect_events()  # clear creation event
        tc.deny("no role")
        events = tc.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ToolCallDeniedEvent)
        assert events[0].reason == "no role"

    def test_request_approval_emits_approval_requested(self):
        tc = _approval_call()
        tc.collect_events()
        tc.request_approval()
        events = tc.collect_events()
        assert len(events) == 1
        e = events[0]
        assert isinstance(e, ApprovalRequestedEvent)
        assert e.approval_id == tc.approval.approval_id

    def test_approve_emits_approved_event(self):
        tc = _approval_call()
        tc.request_approval()
        tc.collect_events()
        tc.approve("admin-1", "looks good")
        events = tc.collect_events()
        assert len(events) == 1
        e = events[0]
        assert isinstance(e, ToolCallApprovedEvent)
        assert e.approver_id == "admin-1"

    def test_reject_emits_rejected_event(self):
        tc = _approval_call()
        tc.request_approval()
        tc.collect_events()
        tc.reject("admin-1", "fraud")
        events = tc.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ToolCallRejectedEvent)

    def test_record_execution_emits_executed_event(self):
        tc = _allow_call()
        tc.collect_events()
        tc.record_execution(_ok_result())
        events = tc.collect_events()
        assert len(events) == 1
        e = events[0]
        assert isinstance(e, ToolCallExecutedEvent)
        assert e.execution_status == "SIMULATED"
        assert e.actual_cost == 0.01
        assert e.duration_ms == 12

    def test_full_approval_flow_emits_in_order(self):
        tc = _approval_call()
        tc.request_approval()
        tc.approve("admin-1")
        tc.record_execution(_ok_result())
        events = tc.collect_events()
        assert len(events) == 4
        assert isinstance(events[0], ToolCallCreatedEvent)
        assert isinstance(events[1], ApprovalRequestedEvent)
        assert isinstance(events[2], ToolCallApprovedEvent)
        assert isinstance(events[3], ToolCallExecutedEvent)
