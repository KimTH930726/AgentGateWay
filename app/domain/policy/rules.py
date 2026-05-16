"""
Policy rules — Chain of Responsibility pattern.
Each rule either returns a PolicyResult to short-circuit evaluation,
or returns None to pass control to the next rule.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.domain.agent_tool_policy.agent_tool_policy import (
    PolicyDecisionForTool,
    evaluate_agent_tool_policies,
)
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


class AgentToolPolicyRule(PolicyRule):
    """Enforces the per-agent allowlist / denylist. DENY beats ALLOW."""

    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        decision = evaluate_agent_tool_policies(ctx.agent_tool_policies, ctx.tool.name)
        if decision == PolicyDecisionForTool.DENIED_BY_DENYLIST:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Tool '{ctx.tool.name}' is on the denylist for agent '{ctx.agent.agent_id}'",
            )
        if decision == PolicyDecisionForTool.DENIED_BY_ALLOWLIST_OMISSION:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Tool '{ctx.tool.name}' is not on the allowlist for agent '{ctx.agent.agent_id}'",
            )
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
    """Hard per-tool daily cost limit. Exceeded → DENY."""

    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if ctx.daily_usage_cost >= ctx.tool.daily_cost_limit:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Daily cost limit exceeded: {ctx.tool.daily_cost_limit}",
            )
        return None


class ToolCostWarnRule(PolicyRule):
    """Soft per-tool threshold (between warn and hard) → REQUIRE_APPROVAL.

    Skipped when no warn_cost_threshold is configured on the tool, so existing
    tools without the field behave exactly as before.
    """

    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        warn = ctx.tool.warn_cost_threshold
        if warn is None:
            return None
        # CostLimitRule already DENIED if usage >= hard limit. This rule fires
        # only in the warn..hard band.
        if warn <= ctx.daily_usage_cost < ctx.tool.daily_cost_limit:
            return PolicyResult(
                PolicyDecision.REQUIRE_APPROVAL,
                f"Tool '{ctx.tool.name}' daily spend "
                f"{ctx.daily_usage_cost} crossed warn threshold {warn}",
            )
        return None


class AgentBudgetHardRule(PolicyRule):
    """Per-agent daily cost cap. Exceeded → DENY."""

    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        limit = ctx.agent.daily_cost_limit
        usage = ctx.agent_daily_cost
        if limit is None or usage is None:
            return None
        if usage >= limit:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Agent '{ctx.agent.agent_id}' daily cost limit exceeded: {limit}",
            )
        return None


class AgentBudgetWarnRule(PolicyRule):
    """Per-agent daily warn threshold → REQUIRE_APPROVAL."""

    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        warn = ctx.agent.daily_cost_warn_threshold
        limit = ctx.agent.daily_cost_limit
        usage = ctx.agent_daily_cost
        if warn is None or usage is None:
            return None
        # Skip if hard limit will deny anyway (handled by AgentBudgetHardRule).
        if limit is not None and usage >= limit:
            return None
        if usage >= warn:
            return PolicyResult(
                PolicyDecision.REQUIRE_APPROVAL,
                f"Agent '{ctx.agent.agent_id}' daily spend "
                f"{usage} crossed warn threshold {warn}",
            )
        return None


class AgentTokenLimitRule(PolicyRule):
    """Per-agent daily token usage cap. Exceeded → DENY."""

    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        limit = ctx.agent.daily_token_limit
        usage = ctx.agent_daily_tokens
        if limit is None or usage is None:
            return None
        if usage >= limit:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Agent '{ctx.agent.agent_id}' daily token limit exceeded: {limit}",
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
    AgentToolPolicyRule(),
    RoleCheckRule(),
    DomainAccessRule(),
    CostLimitRule(),
    ToolCostWarnRule(),
    AgentBudgetHardRule(),
    AgentTokenLimitRule(),
    AgentBudgetWarnRule(),
    ApprovalRequiredRule(),
]
