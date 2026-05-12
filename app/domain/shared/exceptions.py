class AgentGateError(Exception):
    """Base for all application errors."""
    code: str = "INTERNAL_ERROR"


class DomainError(AgentGateError):
    """Invariant or state-machine violation inside an aggregate."""
    code: str = "DOMAIN_ERROR"


class NotFoundError(AgentGateError):
    """Requested resource does not exist."""
    code: str = "NOT_FOUND"


class PolicyViolationError(DomainError):
    """Tool call blocked by policy engine."""
    code: str = "POLICY_VIOLATION"


class ConflictError(AgentGateError):
    """Resource already exists."""
    code: str = "CONFLICT"
