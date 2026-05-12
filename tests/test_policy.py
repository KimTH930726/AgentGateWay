import pytest

from app.domain.agent.agent import Agent
from app.domain.enums import PolicyDecision, RiskLevel
from app.domain.policy.policy_engine import PolicyContext, PolicyEngine
from app.domain.tool.tool import Tool
from app.domain.user.user import User


@pytest.fixture
def engine():
    return PolicyEngine()


def _ctx(
    tool_enabled=True,
    risk_level=RiskLevel.LOW,
    approval_required=False,
    required_role="cs_agent",
    user_roles=None,
    agent_domains=None,
    tool_domain="order",
    user_enabled=True,
    agent_enabled=True,
    daily_cost=0.0,
    daily_limit=1000.0,
) -> PolicyContext:
    tool = Tool(
        tool_id="t1", name="refund_order", description="",
        domain=tool_domain, risk_level=risk_level,
        required_role=required_role, approval_required=approval_required,
        sandbox_supported=True, daily_cost_limit=daily_limit, enabled=tool_enabled,
    )
    agent = Agent(
        agent_id="a1", name="CS Agent",
        allowed_domains=agent_domains or ["order"],
        enabled=agent_enabled,
    )
    user = User(user_id="u1", roles=user_roles or ["cs_agent"], enabled=user_enabled)
    return PolicyContext(tool=tool, agent=agent, user=user, daily_usage_cost=daily_cost)


def test_allow_low_risk(engine):
    assert engine.evaluate(_ctx()).decision == PolicyDecision.ALLOW


def test_deny_disabled_tool(engine):
    assert engine.evaluate(_ctx(tool_enabled=False)).decision == PolicyDecision.DENY


def test_deny_disabled_user(engine):
    assert engine.evaluate(_ctx(user_enabled=False)).decision == PolicyDecision.DENY


def test_deny_missing_role(engine):
    assert engine.evaluate(_ctx(user_roles=["viewer"])).decision == PolicyDecision.DENY


def test_deny_domain_not_allowed(engine):
    assert engine.evaluate(_ctx(agent_domains=["billing"])).decision == PolicyDecision.DENY


def test_deny_cost_limit_exceeded(engine):
    assert engine.evaluate(_ctx(daily_cost=1000.0, daily_limit=1000.0)).decision == PolicyDecision.DENY


def test_require_approval_high_risk(engine):
    assert engine.evaluate(_ctx(risk_level=RiskLevel.HIGH)).decision == PolicyDecision.REQUIRE_APPROVAL


def test_require_approval_flag(engine):
    assert engine.evaluate(_ctx(approval_required=True)).decision == PolicyDecision.REQUIRE_APPROVAL


def test_medium_risk_allows_without_flag(engine):
    result = engine.evaluate(_ctx(risk_level=RiskLevel.MEDIUM, approval_required=False))
    assert result.decision == PolicyDecision.ALLOW
