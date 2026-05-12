"""Lightweight domain events emitted by the ToolCall aggregate."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainEvent:
    request_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class ToolCallCreatedEvent(DomainEvent):
    tool_name: str
    agent_id: str
    user_id: str


@dataclass(frozen=True)
class ApprovalRequestedEvent(DomainEvent):
    approval_id: str


@dataclass(frozen=True)
class ToolCallApprovedEvent(DomainEvent):
    approver_id: str


@dataclass(frozen=True)
class ToolCallRejectedEvent(DomainEvent):
    approver_id: str


@dataclass(frozen=True)
class ToolCallDeniedEvent(DomainEvent):
    reason: str


@dataclass(frozen=True)
class ToolCallExecutedEvent(DomainEvent):
    execution_status: str
    actual_cost: float
    duration_ms: int
