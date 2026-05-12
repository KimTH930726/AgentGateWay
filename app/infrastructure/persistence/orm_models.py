import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum, Float,
    ForeignKey, Index, Integer, JSON, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.persistence.database import Base
from app.domain.enums import ApprovalStatus, ExecutionStatus, PolicyDecision, RiskLevel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ToolORM(Base):
    __tablename__ = "tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    domain = Column(String(64), nullable=False)
    risk_level = Column(SAEnum(RiskLevel), nullable=False)
    required_role = Column(String(64), nullable=False)
    approval_required = Column(Boolean, nullable=False, default=False)
    sandbox_supported = Column(Boolean, nullable=False, default=False)
    daily_cost_limit = Column(Float, nullable=False, default=0.0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class AgentORM(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    allowed_domains = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class UserORM(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    roles = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class ToolCallORM(Base):
    __tablename__ = "tool_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(64), unique=True, nullable=False, index=True)
    agent_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    tool_name = Column(String(128), nullable=False)
    input_data = Column(JSON, nullable=False)
    input_hash = Column(String(64), nullable=False)
    risk_level = Column(SAEnum(RiskLevel), nullable=False)
    policy_decision = Column(SAEnum(PolicyDecision), nullable=False)
    approval_status = Column(SAEnum(ApprovalStatus), nullable=True)
    execution_status = Column(SAEnum(ExecutionStatus), nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    trace_id = Column(String(64), nullable=False, default="", index=True)
    policy_reason = Column(Text, nullable=False, default="")
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # selectin avoids N+1 when iterating a list of ToolCallORM rows
    approval = relationship("ApprovalORM", back_populates="tool_call", uselist=False, lazy="selectin")

    __table_args__ = (
        # speeds up get_daily_cost aggregation query
        Index("ix_tool_calls_tool_name_created_at", "tool_name", "created_at"),
    )


class ApprovalORM(Base):
    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_call_id = Column(UUID(as_uuid=True), ForeignKey("tool_calls.id"), nullable=False, index=True)
    approver_id = Column(String(64), nullable=True)
    status = Column(SAEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    tool_call = relationship("ToolCallORM", back_populates="approval")
