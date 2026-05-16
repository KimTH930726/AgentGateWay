from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SIMULATED = "SIMULATED"


class AgentToolPolicyType(str, Enum):
    """Per-agent allowlist / denylist entry kind."""
    ALLOW = "ALLOW"
    DENY = "DENY"


class GovernanceEntityType(str, Enum):
    """Subject of a configuration change log entry."""
    TOOL = "TOOL"
    AGENT = "AGENT"
    USER = "USER"
    AGENT_TOOL_POLICY = "AGENT_TOOL_POLICY"


class ChangeType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class RuleOutcome(str, Enum):
    """Per-rule outcome inside a policy evaluation trace."""
    PASS = "PASS"           # rule did not short-circuit
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
