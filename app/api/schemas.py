from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.domain.enums import (
    AgentToolPolicyType,
    ApprovalStatus,
    ChangeType,
    ExecutionStatus,
    GovernanceEntityType,
    PolicyDecision,
    RiskLevel,
    RuleOutcome,
)


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
    warn_cost_threshold: Optional[float] = None


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    required_role: Optional[str] = None
    approval_required: Optional[bool] = None
    sandbox_supported: Optional[bool] = None
    daily_cost_limit: Optional[float] = None
    warn_cost_threshold: Optional[float] = None
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
    warn_cost_threshold: Optional[float] = None
    enabled: bool

    model_config = {"from_attributes": True}


# --- Agent ----------------------------------------------------------------

class AgentCreate(BaseModel):
    agent_id: str
    name: str
    allowed_domains: List[str]
    daily_cost_limit: Optional[float] = None
    monthly_cost_limit: Optional[float] = None
    daily_token_limit: Optional[int] = None
    daily_cost_warn_threshold: Optional[float] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    enabled: Optional[bool] = None
    daily_cost_limit: Optional[float] = None
    monthly_cost_limit: Optional[float] = None
    daily_token_limit: Optional[int] = None
    daily_cost_warn_threshold: Optional[float] = None


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    allowed_domains: List[str]
    enabled: bool
    daily_cost_limit: Optional[float] = None
    monthly_cost_limit: Optional[float] = None
    daily_token_limit: Optional[int] = None
    daily_cost_warn_threshold: Optional[float] = None

    model_config = {"from_attributes": True}


class AgentUsageResponse(BaseModel):
    agent_id: str
    daily_cost: float
    monthly_cost: float
    daily_tokens: int
    daily_cost_limit: Optional[float] = None
    daily_cost_warn_threshold: Optional[float] = None
    daily_token_limit: Optional[int] = None


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

class CandidateToolPayload(BaseModel):
    tool_name: str
    reason_not_selected: str = ""


class InvokeRequest(BaseModel):
    agent_id: str
    user_id: str
    tool_name: str
    input: Dict[str, Any]
    trace_id: Optional[str] = None
    selected_reason: Optional[str] = None
    candidates: Optional[List[CandidateToolPayload]] = None


class RuleEvaluationResponse(BaseModel):
    rule: str
    outcome: RuleOutcome
    reason: str = ""


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
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None
    selected_reason: Optional[str] = None
    candidates: Optional[List[CandidateToolPayload]] = None
    rule_trace: List[RuleEvaluationResponse] = []


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
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    executed_at: Optional[datetime] = None
    selected_reason: Optional[str] = None
    candidates: Optional[List[CandidateToolPayload]] = None
    rule_trace: List[RuleEvaluationResponse] = []


class AuditLogPage(BaseModel):
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int
    has_next: bool


# --- Agent Tool Policy ----------------------------------------------------

class AgentToolPolicyCreate(BaseModel):
    agent_id: str
    tool_name: str
    policy_type: AgentToolPolicyType
    reason: str = ""
    created_by: str = ""


class AgentToolPolicyUpdate(BaseModel):
    enabled: Optional[bool] = None
    reason: Optional[str] = None
    changed_by: Optional[str] = None
    change_reason: Optional[str] = None


class AgentToolPolicyDeleteRequest(BaseModel):
    changed_by: Optional[str] = None
    change_reason: Optional[str] = None


class AgentToolPolicyResponse(BaseModel):
    policy_id: str
    agent_id: str
    tool_name: str
    policy_type: AgentToolPolicyType
    enabled: bool
    reason: str = ""
    created_by: str = ""
    created_at: datetime


# --- Governance / Change Log ---------------------------------------------

class ChangeLogResponse(BaseModel):
    log_id: str
    entity_type: GovernanceEntityType
    entity_key: str
    change_type: ChangeType
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    reason: str = ""
    changed_by: str = ""
    changed_at: datetime


class ChangeLogPageResponse(BaseModel):
    items: List[ChangeLogResponse]
    total: int
    limit: int
    offset: int
    has_next: bool
