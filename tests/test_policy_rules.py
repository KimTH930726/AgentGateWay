"""
Isolation tests for each PolicyRule — verifies that each rule triggers
independently and that custom rule chains work correctly.
"""
import pytest

from app.domain.agent.agent import Agent
from app.domain.enums import PolicyDecision, RiskLevel
from app.domain.policy.context import PolicyContext
from app.domain.policy.policy_engine import PolicyEngine
from app.domain.policy.rules import (
    AgentEnabledRule,
    ApprovalRequiredRule,
    CostLimitRule,
    DEFAULT_RULES,
    DomainAccessRule,
    RoleCheckRule,
    ToolEnabledRule,
    UserEnabledRule,
)
from app.domain.tool.tool import Tool
from app.domain.user.user import User


def _tool(
    enabled=True,
    risk_level=RiskLevel.LOW,
    approval_required=False,
    required_role="cs_agent",
    domain="order",
    daily_cost_limit=1000.0,
) -> Tool:
    return Tool(
        tool_id="t1", name="t", description="",
        domain=domain, risk_level=risk_level,
        required_role=required_role, approval_required=approval_required,
        sandbox_supported=True, daily_cost_limit=daily_cost_limit, enabled=enabled,
    )


def _agent(allowed_domains=None, enabled=True) -> Agent:
    return Agent(agent_id="a1", name="A", allowed_domains=allowed_domains or ["order"], enabled=enabled)


def _user(roles=None, enabled=True) -> User:
    return User(user_id="u1", roles=roles or ["cs_agent"], enabled=enabled)


def _ctx(**kwargs) -> PolicyContext:
    tool_kwargs = {k: v for k, v in kwargs.items() if k in ("enabled", "risk_level", "approval_required",
                                                              "required_role", "domain", "daily_cost_limit")}
    tool_kwargs.setdefault("enabled", kwargs.get("tool_enabled", True))
    agent = _agent(
        allowed_domains=kwargs.get("agent_domains"),
        enabled=kwargs.get("agent_enabled", True),
    )
    user = _user(roles=kwargs.get("user_roles"), enabled=kwargs.get("user_enabled", True))
    tool = _tool(
        enabled=kwargs.get("tool_enabled", True),
        risk_level=kwargs.get("risk_level", RiskLevel.LOW),
        approval_required=kwargs.get("approval_required", False),
        required_role=kwargs.get("required_role", "cs_agent"),
        domain=kwargs.get("domain", "order"),
        daily_cost_limit=kwargs.get("daily_cost_limit", 1000.0),
    )
    return PolicyContext(tool=tool, agent=agent, user=user, daily_usage_cost=kwargs.get("daily_cost", 0.0))


# --- ToolEnabledRule -------------------------------------------------------

class TestToolEnabledRule:
    def test_denies_when_disabled(self):
        result = ToolEnabledRule().evaluate(_ctx(tool_enabled=False))
        assert result is not None
        assert result.decision == PolicyDecision.DENY

    def test_passes_when_enabled(self):
        assert ToolEnabledRule().evaluate(_ctx(tool_enabled=True)) is None


# --- UserEnabledRule -------------------------------------------------------

class TestUserEnabledRule:
    def test_denies_disabled_user(self):
        result = UserEnabledRule().evaluate(_ctx(user_enabled=False))
        assert result is not None and result.decision == PolicyDecision.DENY

    def test_passes_enabled_user(self):
        assert UserEnabledRule().evaluate(_ctx(user_enabled=True)) is None


# --- AgentEnabledRule ------------------------------------------------------

class TestAgentEnabledRule:
    def test_denies_disabled_agent(self):
        result = AgentEnabledRule().evaluate(_ctx(agent_enabled=False))
        assert result is not None and result.decision == PolicyDecision.DENY

    def test_passes_enabled_agent(self):
        assert AgentEnabledRule().evaluate(_ctx(agent_enabled=True)) is None


# --- RoleCheckRule ---------------------------------------------------------

class TestRoleCheckRule:
    def test_denies_missing_role(self):
        result = RoleCheckRule().evaluate(_ctx(required_role="admin", user_roles=["viewer"]))
        assert result is not None and result.decision == PolicyDecision.DENY

    def test_passes_with_correct_role(self):
        assert RoleCheckRule().evaluate(_ctx(required_role="cs_agent", user_roles=["cs_agent"])) is None

    def test_passes_when_user_has_exact_required_role(self):
        assert RoleCheckRule().evaluate(_ctx(required_role="admin", user_roles=["admin", "cs_agent"])) is None


# --- DomainAccessRule ------------------------------------------------------

class TestDomainAccessRule:
    def test_denies_out_of_domain(self):
        result = DomainAccessRule().evaluate(_ctx(domain="billing", agent_domains=["order"]))
        assert result is not None and result.decision == PolicyDecision.DENY

    def test_passes_allowed_domain(self):
        assert DomainAccessRule().evaluate(_ctx(domain="order", agent_domains=["order"])) is None


# --- CostLimitRule ---------------------------------------------------------

class TestCostLimitRule:
    def test_denies_at_limit(self):
        result = CostLimitRule().evaluate(_ctx(daily_cost=1000.0, daily_cost_limit=1000.0))
        assert result is not None and result.decision == PolicyDecision.DENY

    def test_denies_over_limit(self):
        result = CostLimitRule().evaluate(_ctx(daily_cost=1500.0, daily_cost_limit=1000.0))
        assert result is not None and result.decision == PolicyDecision.DENY

    def test_passes_under_limit(self):
        assert CostLimitRule().evaluate(_ctx(daily_cost=999.99, daily_cost_limit=1000.0)) is None


# --- ApprovalRequiredRule --------------------------------------------------

class TestApprovalRequiredRule:
    def test_requires_approval_for_high_risk(self):
        result = ApprovalRequiredRule().evaluate(_ctx(risk_level=RiskLevel.HIGH))
        assert result is not None and result.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_requires_approval_when_flag_set(self):
        result = ApprovalRequiredRule().evaluate(_ctx(approval_required=True))
        assert result is not None and result.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_allows_low_risk_no_flag(self):
        assert ApprovalRequiredRule().evaluate(_ctx(risk_level=RiskLevel.LOW, approval_required=False)) is None

    def test_allows_medium_risk_no_flag(self):
        assert ApprovalRequiredRule().evaluate(_ctx(risk_level=RiskLevel.MEDIUM, approval_required=False)) is None


# --- PolicyEngine with custom rules ----------------------------------------

class TestPolicyEngineCustomRules:
    def test_empty_rules_always_allow(self):
        engine = PolicyEngine(rules=[])
        result = engine.evaluate(_ctx(tool_enabled=False))
        assert result.decision == PolicyDecision.ALLOW

    def test_single_rule_chain(self):
        engine = PolicyEngine(rules=[ToolEnabledRule()])
        assert engine.evaluate(_ctx(tool_enabled=False)).decision == PolicyDecision.DENY
        assert engine.evaluate(_ctx(tool_enabled=True)).decision == PolicyDecision.ALLOW

    def test_rule_short_circuits_on_first_match(self):
        """ToolEnabledRule fires first; later rules are never reached."""
        engine = PolicyEngine(rules=[ToolEnabledRule(), ApprovalRequiredRule()])
        # Tool is disabled AND high-risk: should DENY (not REQUIRE_APPROVAL)
        result = engine.evaluate(_ctx(tool_enabled=False, risk_level=RiskLevel.HIGH))
        assert result.decision == PolicyDecision.DENY

    def test_default_rules_order(self):
        assert len(DEFAULT_RULES) == 7
