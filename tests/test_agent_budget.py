"""
Integration tests for per-agent budget enforcement.
Covers hard limit (DENY), soft warn threshold (REQUIRE_APPROVAL), and
the /agents/{id}/usage endpoint.
"""
from app.domain.agent.agent import Agent
from app.domain.enums import PolicyDecision, RiskLevel
from app.domain.policy.context import PolicyContext
from app.domain.policy.rules import (
    AgentBudgetHardRule,
    AgentBudgetWarnRule,
    AgentTokenLimitRule,
    ToolCostWarnRule,
)
from app.domain.tool.tool import Tool
from app.domain.user.user import User
from tests.conftest import seed_agent, seed_tool, seed_user


# ---------------------------------------------------------------------------
# Rule-level unit tests
# ---------------------------------------------------------------------------

def _ctx(
    *,
    daily_cost_limit=None,
    daily_cost_warn_threshold=None,
    daily_token_limit=None,
    agent_daily_cost=None,
    agent_daily_tokens=None,
    tool_warn=None,
    tool_daily_cost_limit=1000.0,
    daily_usage_cost=0.0,
) -> PolicyContext:
    tool = Tool(
        tool_id="t1", name="t", description="", domain="order",
        risk_level=RiskLevel.LOW, required_role="cs_agent",
        approval_required=False, sandbox_supported=True,
        daily_cost_limit=tool_daily_cost_limit, enabled=True,
        warn_cost_threshold=tool_warn,
    )
    agent = Agent(
        agent_id="a1", name="A", allowed_domains=["order"], enabled=True,
        daily_cost_limit=daily_cost_limit,
        daily_cost_warn_threshold=daily_cost_warn_threshold,
        daily_token_limit=daily_token_limit,
    )
    user = User(user_id="u1", roles=["cs_agent"], enabled=True)
    return PolicyContext(
        tool=tool, agent=agent, user=user,
        daily_usage_cost=daily_usage_cost,
        agent_daily_cost=agent_daily_cost,
        agent_daily_tokens=agent_daily_tokens,
    )


class TestAgentBudgetHardRule:
    def test_skipped_when_limit_or_usage_unset(self):
        assert AgentBudgetHardRule().evaluate(_ctx()) is None
        assert AgentBudgetHardRule().evaluate(_ctx(daily_cost_limit=10)) is None
        assert AgentBudgetHardRule().evaluate(_ctx(agent_daily_cost=10)) is None

    def test_denies_when_usage_at_or_above_limit(self):
        r = AgentBudgetHardRule().evaluate(
            _ctx(daily_cost_limit=10.0, agent_daily_cost=10.0)
        )
        assert r is not None and r.decision == PolicyDecision.DENY

    def test_passes_below_limit(self):
        assert AgentBudgetHardRule().evaluate(
            _ctx(daily_cost_limit=10.0, agent_daily_cost=5.0)
        ) is None


class TestAgentBudgetWarnRule:
    def test_skipped_without_warn_threshold(self):
        assert AgentBudgetWarnRule().evaluate(
            _ctx(daily_cost_limit=10.0, agent_daily_cost=5.0)
        ) is None

    def test_requires_approval_in_warn_band(self):
        r = AgentBudgetWarnRule().evaluate(
            _ctx(
                daily_cost_limit=10.0,
                daily_cost_warn_threshold=5.0,
                agent_daily_cost=6.0,
            )
        )
        assert r is not None and r.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_defers_to_hard_rule_when_over_limit(self):
        # Warn rule must not fire when hard limit is already breached — the
        # hard rule runs earlier in the chain and will DENY anyway.
        assert AgentBudgetWarnRule().evaluate(
            _ctx(
                daily_cost_limit=10.0,
                daily_cost_warn_threshold=5.0,
                agent_daily_cost=11.0,
            )
        ) is None


class TestAgentTokenLimitRule:
    def test_denies_at_token_cap(self):
        r = AgentTokenLimitRule().evaluate(
            _ctx(daily_token_limit=1000, agent_daily_tokens=1000)
        )
        assert r is not None and r.decision == PolicyDecision.DENY

    def test_passes_below_cap(self):
        assert AgentTokenLimitRule().evaluate(
            _ctx(daily_token_limit=1000, agent_daily_tokens=999)
        ) is None


class TestToolCostWarnRule:
    def test_escalates_to_approval_in_warn_band(self):
        r = ToolCostWarnRule().evaluate(
            _ctx(tool_warn=500.0, tool_daily_cost_limit=1000.0, daily_usage_cost=600.0)
        )
        assert r is not None and r.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_passes_below_warn(self):
        assert ToolCostWarnRule().evaluate(
            _ctx(tool_warn=500.0, tool_daily_cost_limit=1000.0, daily_usage_cost=100.0)
        ) is None


# ---------------------------------------------------------------------------
# Integration: tool warn threshold flips ALLOW → REQUIRE_APPROVAL
# ---------------------------------------------------------------------------

def _invoke(client):
    return client.post("/api/v1/gateway/invoke", json={
        "agent_id": "cs-agent-001",
        "user_id": "user-001",
        "tool_name": "refund_order",
        "input": {"order_id": "ORDER-1", "amount": 1000},
    })


class TestToolWarnThresholdIntegration:
    def test_warn_threshold_seeds_correctly(self, client):
        # Tool with a high daily limit but a warn threshold of 0 forces every
        # call into the warn band, so the first invoke escalates to approval.
        client.post("/api/v1/tools", json={
            "tool_id": "tool-refund", "name": "refund_order",
            "description": "x", "domain": "order",
            "risk_level": "LOW", "required_role": "cs_agent",
            "approval_required": False, "sandbox_supported": True,
            "daily_cost_limit": 1000.0,
            "warn_cost_threshold": 0.0,
        })
        seed_agent(client)
        seed_user(client)
        body = _invoke(client).json()
        # warn threshold is 0 and usage is 0; 0 >= 0 → REQUIRE_APPROVAL
        assert body["policy_decision"] == "REQUIRE_APPROVAL"


# ---------------------------------------------------------------------------
# Integration: agent usage endpoint
# ---------------------------------------------------------------------------

class TestAgentUsageEndpoint:
    def test_usage_starts_at_zero(self, client):
        seed_agent(client, daily_cost_limit=100.0, daily_cost_warn_threshold=80.0)
        body = client.get("/api/v1/agents/cs-agent-001/usage").json()
        assert body["daily_cost"] == 0.0
        assert body["daily_tokens"] == 0
        assert body["daily_cost_limit"] == 100.0
        assert body["daily_cost_warn_threshold"] == 80.0

    def test_usage_accumulates_after_invoke(self, client):
        seed_tool(client, risk_level="LOW", approval_required=False)
        seed_agent(client)
        seed_user(client)
        client.post("/api/v1/gateway/invoke", json={
            "agent_id": "cs-agent-001", "user_id": "user-001",
            "tool_name": "refund_order",
            "input": {"order_id": "x", "amount": 1},
        })
        usage = client.get("/api/v1/agents/cs-agent-001/usage").json()
        assert usage["daily_cost"] > 0
