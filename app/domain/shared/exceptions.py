class AgentGateError(Exception):
    """Base for all application errors."""


class DomainError(AgentGateError):
    """Invariant or state-machine violation inside an aggregate."""


class NotFoundError(AgentGateError):
    """Requested resource does not exist."""


class PolicyViolationError(DomainError):
    """Tool call blocked by policy engine."""
