from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.domain.enums import ApprovalStatus, ExecutionStatus, PolicyDecision, RiskLevel


# --- Error ----------------------------------------------------------------

class ErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    DOMAIN_ERROR = "DOMAIN_ERROR"
    CONFLICT = "CONFLICT"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str


# --- Tool -----------------------------------------------------------------

class ToolCreate(BaseModel):
    tool_id: str
    name: str
    description: str
    domain: str
    risk_level: RiskLevel
    required_role: str
    approval_required: bool = False
    sandbox_supported: bool = False
    daily_cost_limit: float = 1000.0


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    required_role: Optional[str] = None
    approval_required: Optional[bool] = None
    sandbox_supported: Optional[bool] = None
    daily_cost_limit: Optional[float] = None
    enabled: Optional[bool] = None


class ToolResponse(BaseModel):
    tool_id: str
    name: str
    description: str
    domain: str
    risk_level: RiskLevel
    required_role: str
    approval_required: bool
    sandbox_supported: bool
    daily_cost_limit: float
    enabled: bool

    model_config = {"from_attributes": True}


# --- Agent ----------------------------------------------------------------

class AgentCreate(BaseModel):
    agent_id: str
    name: str
    allowed_domains: List[str]


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    allowed_domains: List[str]
    enabled: bool

    model_config = {"from_attributes": True}


# --- User -----------------------------------------------------------------

class UserCreate(BaseModel):
    user_id: str
    roles: List[str]


class UserResponse(BaseModel):
    user_id: str
    roles: List[str]
    enabled: bool

    model_config = {"from_attributes": True}


# --- Gateway --------------------------------------------------------------

class InvokeRequest(BaseModel):
    agent_id: str
    user_id: str
    tool_name: str
    input: Dict[str, Any]
    trace_id: Optional[str] = None


class InvokeResponse(BaseModel):
    request_id: str
    tool_name: str
    policy_decision: PolicyDecision
    policy_reason: str = ""
    trace_id: str = ""
    approval_status: Optional[ApprovalStatus] = None
    execution_status: Optional[ExecutionStatus] = None
    risk_level: RiskLevel
    estimated_cost: float
    actual_cost: Optional[float] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None


# --- Approval -------------------------------------------------------------

class ApprovalActionRequest(BaseModel):
    approver_id: str
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Approval context — includes relevant ToolCall fields."""
    approval_id: str
    request_id: str
    agent_id: str
    user_id: str
    tool_name: str
    risk_level: RiskLevel
    status: ApprovalStatus
    approver_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None


# --- Audit Log ------------------------------------------------------------

class AuditLogResponse(BaseModel):
    request_id: str
    trace_id: str = ""
    agent_id: str
    user_id: str
    tool_name: str
    input_hash: str
    risk_level: RiskLevel
    policy_decision: PolicyDecision
    policy_reason: str = ""
    approval_status: Optional[ApprovalStatus] = None
    execution_status: Optional[ExecutionStatus] = None
    estimated_cost: float
    actual_cost: Optional[float] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    executed_at: Optional[datetime] = None


class AuditLogPage(BaseModel):
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int
    has_next: bool
