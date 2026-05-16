"""
Tests for decision tracking — selected_reason, candidate tools, rule trace.
Each invocation surfaces the agent's reasoning AND the policy engine's
per-rule trace so reviewers can reconstruct why a call was allowed/denied.
"""
from tests.conftest import seed_agent, seed_tool, seed_user


def _setup(client, risk_level="LOW", approval_required=False):
    seed_tool(client, risk_level=risk_level, approval_required=approval_required)
    seed_agent(client)
    seed_user(client)


def _invoke(client, *, selected_reason=None, candidates=None):
    payload = {
        "agent_id": "cs-agent-001",
        "user_id": "user-001",
        "tool_name": "refund_order",
        "input": {"order_id": "x", "amount": 1},
    }
    if selected_reason is not None:
        payload["selected_reason"] = selected_reason
    if candidates is not None:
        payload["candidates"] = candidates
    return client.post("/api/v1/gateway/invoke", json=payload)


class TestSelectionPersistence:
    def test_selected_reason_persisted(self, client):
        _setup(client)
        body = _invoke(
            client,
            selected_reason="user asked to refund, refund_order is the canonical tool",
        ).json()
        assert body["selected_reason"].startswith("user asked to refund")

        audit = client.get(f"/api/v1/audit-logs/{body['request_id']}").json()
        assert audit["selected_reason"].startswith("user asked to refund")

    def test_candidates_persisted(self, client):
        _setup(client)
        body = _invoke(client, candidates=[
            {"tool_name": "refund_order", "reason_not_selected": ""},
            {"tool_name": "cancel_order", "reason_not_selected": "order already shipped"},
        ]).json()
        assert body["candidates"] is not None
        names = [c["tool_name"] for c in body["candidates"]]
        assert "cancel_order" in names

        audit = client.get(f"/api/v1/audit-logs/{body['request_id']}").json()
        cancel = next(c for c in audit["candidates"] if c["tool_name"] == "cancel_order")
        assert cancel["reason_not_selected"] == "order already shipped"

    def test_no_selection_data_is_optional(self, client):
        _setup(client)
        body = _invoke(client).json()
        assert body["selected_reason"] is None
        assert body["candidates"] is None


class TestRuleTrace:
    def test_allow_trace_lists_all_passing_rules(self, client):
        _setup(client)
        body = _invoke(client).json()
        trace = body["rule_trace"]
        names = [step["rule"] for step in trace]
        # Every rule should appear with outcome PASS when nothing fires.
        assert "ToolEnabledRule" in names
        assert "AgentToolPolicyRule" in names
        assert "ApprovalRequiredRule" in names
        assert all(step["outcome"] == "PASS" for step in trace)

    def test_deny_trace_truncates_at_first_match(self, client):
        # User missing the required role triggers RoleCheckRule.
        seed_tool(client, required_role="admin")
        seed_agent(client)
        seed_user(client, roles=["viewer"])
        body = _invoke(client).json()

        trace = body["rule_trace"]
        # The rule that fired must be the final entry, marked DENY.
        last = trace[-1]
        assert last["outcome"] == "DENY"
        assert last["rule"] == "RoleCheckRule"
        assert "role" in last["reason"].lower()

    def test_trace_persisted_to_audit_log(self, client):
        _setup(client)
        body = _invoke(client).json()
        audit = client.get(f"/api/v1/audit-logs/{body['request_id']}").json()
        assert len(audit["rule_trace"]) > 0
        assert audit["rule_trace"][0]["rule"] == "ToolEnabledRule"
