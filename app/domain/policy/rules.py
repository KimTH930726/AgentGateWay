"""
Policy rules — Chain of Responsibility pattern.
Each rule either returns a PolicyResult to short-circuit evaluation,
or returns None to pass control to the next rule.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.domain.enums import PolicyDecision
from app.domain.policy.context import PolicyContext, PolicyResult


class PolicyRule(ABC):
    """Single-responsibility policy check. Return None to continue the chain."""

    @abstractmethod
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        ...


class ToolEnabledRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if not ctx.tool.enabled:
            return PolicyResult(PolicyDecision.DENY, "Tool is disabled")
        return None


class UserEnabledRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if not ctx.user.enabled:
            return PolicyResult(PolicyDecision.DENY, "User account is disabled")
        return None


class AgentEnabledRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if not ctx.agent.enabled:
            return PolicyResult(PolicyDecision.DENY, "Agent is disabled")
        return None


class RoleCheckRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if not ctx.user.has_role(ctx.tool.required_role):
            return PolicyResult(
                PolicyDecision.DENY,
                f"User lacks required role: {ctx.tool.required_role}",
            )
        return None


class DomainAccessRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if not ctx.agent.can_access_domain(ctx.tool.domain):
            return PolicyResult(
                PolicyDecision.DENY,
                f"Agent not permitted to access domain: {ctx.tool.domain}",
            )
        return None


class CostLimitRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if ctx.daily_usage_cost >= ctx.tool.daily_cost_limit:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Daily cost limit exceeded: {ctx.tool.daily_cost_limit}",
            )
        return None


class ApprovalRequiredRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if ctx.tool.requires_approval():
            return PolicyResult(
                PolicyDecision.REQUIRE_APPROVAL,
                f"Tool risk level {ctx.tool.risk_level} requires human approval",
            )
        return None


DEFAULT_RULES: list[PolicyRule] = [
    ToolEnabledRule(),
    UserEnabledRule(),
    AgentEnabledRule(),
    RoleCheckRule(),
    DomainAccessRule(),
    CostLimitRule(),
    ApprovalRequiredRule(),
]
