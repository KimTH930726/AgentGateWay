"""
Integration tests for Agent Tool Policy — per-agent allowlist / denylist.
Verifies DENY > ALLOW precedence and integration with the gateway.
"""
import pytest

from app.domain.agent_tool_policy.agent_tool_policy import (
    AgentToolPolicy,
    PolicyDecisionForTool,
    evaluate_agent_tool_policies,
)
from app.domain.enums import AgentToolPolicyType
from datetime import datetime, timezone

from tests.conftest import seed_agent, seed_agent_tool_policy, seed_tool, seed_user


# ---------------------------------------------------------------------------
# Pure unit tests for the precedence rule
# ---------------------------------------------------------------------------

def _make(policy_id: str, agent_id: str, tool_name: str, policy_type, enabled=True):
    return AgentToolPolicy(
        policy_id=policy_id,
        agent_id=agent_id,
        tool_name=tool_name,
        policy_type=policy_type,
        enabled=enabled,
        reason="",
        created_by="admin",
        created_at=datetime.now(timezone.utc),
    )


class TestAgentToolPolicyPrecedence:
    def test_no_policies_means_no_opinion(self):
        result = evaluate_agent_tool_policies([], "refund_order")
        assert result == PolicyDecisionForTool.NO_OPINION

    def test_deny_entry_wins_over_allow_entry_for_same_tool(self):
        policies = [
            _make("1", "a1", "refund_order", AgentToolPolicyType.ALLOW),
            _make("2", "a1", "refund_order", AgentToolPolicyType.DENY),
        ]
        assert evaluate_agent_tool_policies(policies, "refund_order") == \
            PolicyDecisionForTool.DENIED_BY_DENYLIST

    def test_disabled_policy_is_ignored(self):
        policies = [
            _make("1", "a1", "refund_order", AgentToolPolicyType.DENY, enabled=False),
        ]
        assert evaluate_agent_tool_policies(policies, "refund_order") == \
            PolicyDecisionForTool.NO_OPINION

    def test_allowlist_blocks_unlisted_tools(self):
        policies = [
            _make("1", "a1", "get_order_detail", AgentToolPolicyType.ALLOW),
        ]
        assert evaluate_agent_tool_policies(policies, "refund_order") == \
            PolicyDecisionForTool.DENIED_BY_ALLOWLIST_OMISSION

    def test_allowlist_permits_listed_tool(self):
        policies = [
            _make("1", "a1", "refund_order", AgentToolPolicyType.ALLOW),
        ]
        assert evaluate_agent_tool_policies(policies, "refund_order") == \
            PolicyDecisionForTool.ALLOWED_BY_ALLOWLIST


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

class TestAgentToolPolicyCRUD:
    def test_create_policy(self, client):
        seed_agent(client)
        resp = client.post("/api/v1/agent-tool-policies", json={
            "agent_id": "cs-agent-001",
            "tool_name": "delete_user",
            "policy_type": "DENY",
            "reason": "destructive tool",
            "created_by": "admin-001",
        })
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["tool_name"] == "delete_user"
        assert body["policy_type"] == "DENY"
        assert body["enabled"] is True
        assert body["reason"] == "destructive tool"
        assert body["created_by"] == "admin-001"
        assert body["policy_id"]

    def test_create_for_unknown_agent_is_404(self, client):
        resp = client.post("/api/v1/agent-tool-policies", json={
            "agent_id": "ghost",
            "tool_name": "x",
            "policy_type": "DENY",
        })
        assert resp.status_code == 404

    def test_duplicate_policy_is_409(self, client):
        seed_agent(client)
        seed_agent_tool_policy(client, tool_name="delete_user", policy_type="DENY")
        resp = client.post("/api/v1/agent-tool-policies", json={
            "agent_id": "cs-agent-001",
            "tool_name": "delete_user",
            "policy_type": "DENY",
        })
        assert resp.status_code == 409

    def test_list_filters_by_agent(self, client):
        seed_agent(client, agent_id="a")
        seed_agent(client, agent_id="b")
        seed_agent_tool_policy(client, agent_id="a", tool_name="t1", policy_type="ALLOW")
        seed_agent_tool_policy(client, agent_id="b", tool_name="t2", policy_type="DENY")

        all_rows = client.get("/api/v1/agent-tool-policies").json()
        assert len(all_rows) == 2

        only_a = client.get("/api/v1/agent-tool-policies?agent_id=a").json()
        assert len(only_a) == 1
        assert only_a[0]["agent_id"] == "a"

    def test_update_toggles_enabled(self, client):
        seed_agent(client)
        created = seed_agent_tool_policy(client, tool_name="delete_user", policy_type="DENY")
        resp = client.patch(
            f"/api/v1/agent-tool-policies/{created['policy_id']}",
            json={"enabled": False, "change_reason": "tool retired"},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_delete_policy(self, client):
        seed_agent(client)
        created = seed_agent_tool_policy(client, tool_name="delete_user", policy_type="DENY")
        resp = client.delete(f"/api/v1/agent-tool-policies/{created['policy_id']}")
        assert resp.status_code == 204
        # subsequent get returns 404
        assert client.get(f"/api/v1/agent-tool-policies/{created['policy_id']}").status_code == 404


# ---------------------------------------------------------------------------
# End-to-end policy enforcement through /gateway/invoke
# ---------------------------------------------------------------------------

def _invoke(client, tool_name="refund_order"):
    return client.post("/api/v1/gateway/invoke", json={
        "agent_id": "cs-agent-001",
        "user_id": "user-001",
        "tool_name": tool_name,
        "input": {"order_id": "ORDER-1234", "amount": 5000, "reason": "test"},
    })


class TestAgentToolPolicyEnforcement:
    def test_deny_entry_blocks_invoke(self, client):
        seed_tool(client, risk_level="LOW", approval_required=False)
        seed_agent(client)
        seed_user(client)
        seed_agent_tool_policy(
            client, tool_name="refund_order", policy_type="DENY",
            reason="too risky for this agent",
        )
        body = _invoke(client).json()
        assert body["policy_decision"] == "DENY"
        assert "denylist" in body["policy_reason"].lower()

    def test_allowlist_permits_listed_tool(self, client):
        seed_tool(client, risk_level="LOW", approval_required=False)
        seed_agent(client)
        seed_user(client)
        seed_agent_tool_policy(
            client, tool_name="refund_order", policy_type="ALLOW",
        )
        body = _invoke(client).json()
        assert body["policy_decision"] == "ALLOW"

    def test_allowlist_blocks_unlisted_tool(self, client):
        seed_tool(client, tool_id="t1", name="refund_order", risk_level="LOW", approval_required=False)
        seed_tool(client, tool_id="t2", name="get_order_detail",
                  risk_level="LOW", approval_required=False)
        seed_agent(client)
        seed_user(client)
        # allowlist exists for a different tool — refund_order must be denied
        seed_agent_tool_policy(
            client, tool_name="get_order_detail", policy_type="ALLOW",
        )
        body = _invoke(client, tool_name="refund_order").json()
        assert body["policy_decision"] == "DENY"
        assert "allowlist" in body["policy_reason"].lower()

    def test_deny_wins_when_both_lists_exist(self, client):
        seed_tool(client, risk_level="LOW", approval_required=False)
        seed_agent(client)
        seed_user(client)
        seed_agent_tool_policy(
            client, tool_name="refund_order", policy_type="ALLOW",
            reason="allowed",
        )
        seed_agent_tool_policy(
            client, tool_name="refund_order", policy_type="DENY",
            reason="emergency block",
        )
        body = _invoke(client).json()
        assert body["policy_decision"] == "DENY"
        assert "denylist" in body["policy_reason"].lower()
