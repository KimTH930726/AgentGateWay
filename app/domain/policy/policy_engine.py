from dataclasses import dataclass

from app.domain.agent.agent import Agent
from app.domain.enums import PolicyDecision, RiskLevel
from app.domain.tool.tool import Tool
from app.domain.user.user import User


@dataclass(frozen=True)
class PolicyContext:
    tool: Tool
    agent: Agent
    user: User
    daily_usage_cost: float


@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str


class PolicyEngine:
    """Domain service — stateless, pure evaluation of access policy."""

    def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        if not ctx.tool.enabled:
            return PolicyResult(PolicyDecision.DENY, "Tool is disabled")

        if not ctx.user.enabled:
            return PolicyResult(PolicyDecision.DENY, "User account is disabled")

        if not ctx.agent.enabled:
            return PolicyResult(PolicyDecision.DENY, "Agent is disabled")

        if not ctx.user.has_role(ctx.tool.required_role):
            return PolicyResult(
                PolicyDecision.DENY,
                f"User lacks required role: {ctx.tool.required_role}",
            )

        if not ctx.agent.can_access_domain(ctx.tool.domain):
            return PolicyResult(
                PolicyDecision.DENY,
                f"Agent not permitted to access domain: {ctx.tool.domain}",
            )

        if ctx.daily_usage_cost >= ctx.tool.daily_cost_limit:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Daily cost limit exceeded: {ctx.tool.daily_cost_limit}",
            )

        if ctx.tool.requires_approval():
            return PolicyResult(
                PolicyDecision.REQUIRE_APPROVAL,
                f"Tool risk level {ctx.tool.risk_level} requires human approval",
            )

        return PolicyResult(PolicyDecision.ALLOW, "All policy checks passed")
