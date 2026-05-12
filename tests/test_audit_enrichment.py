"""
Integration tests for the new audit enrichment fields:
trace_id, policy_reason, duration_ms, and approval EXECUTED state.
"""
from tests.conftest import seed_agent, seed_tool, seed_user


def _setup(client, risk_level="LOW", approval_required=False):
    seed_tool(client, risk_level=risk_level, approval_required=approval_required)
    seed_agent(client)
    seed_user(client)


def _invoke(client, tool_name="refund_order", trace_id=None, **kwargs):
    payload = {
        "agent_id": "cs-agent-001",
        "user_id": "user-001",
        "tool_name": tool_name,
        "input": {"order_id": "ORDER-1234", "amount": 12000},
    }
    if trace_id:
        payload["trace_id"] = trace_id
    payload.update(kwargs)
    return client.post("/api/v1/gateway/invoke", json=payload)


class TestTraceId:
    def test_explicit_trace_id_is_stored(self, client):
        _setup(client, risk_level="LOW")
        body = _invoke(client, trace_id="trace-abc-123").json()
        assert body["trace_id"] == "trace-abc-123"

    def test_auto_generated_trace_id_when_not_provided(self, client):
        _setup(client, risk_level="LOW")
        body = _invoke(client).json()
        assert body["trace_id"]  # non-empty UUID
        assert len(body["trace_id"]) == 36  # UUID format

    def test_trace_id_header_is_accepted(self, client):
        _setup(client, risk_level="LOW")
        body = client.post(
            "/api/v1/gateway/invoke",
            json={
                "agent_id": "cs-agent-001",
                "user_id": "user-001",
                "tool_name": "refund_order",
                "input": {"order_id": "ORDER-1234", "amount": 12000},
            },
            headers={"X-Trace-Id": "header-trace-xyz"},
        ).json()
        assert body["trace_id"] == "header-trace-xyz"

    def test_body_trace_id_overrides_header(self, client):
        _setup(client, risk_level="LOW")
        body = client.post(
            "/api/v1/gateway/invoke",
            json={
                "agent_id": "cs-agent-001",
                "user_id": "user-001",
                "tool_name": "refund_order",
                "input": {"order_id": "ORDER-1234"},
                "trace_id": "body-trace",
            },
            headers={"X-Trace-Id": "header-trace"},
        ).json()
        assert body["trace_id"] == "body-trace"

    def test_trace_id_appears_in_audit_log(self, client):
        _setup(client, risk_level="LOW")
        invoke_body = _invoke(client, trace_id="audit-trace").json()
        request_id = invoke_body["request_id"]
        audit = client.get(f"/api/v1/audit-logs/{request_id}").json()
        assert audit["trace_id"] == "audit-trace"


class TestPolicyReason:
    def test_allow_policy_reason_in_response(self, client):
        _setup(client, risk_level="LOW")
        body = _invoke(client).json()
        assert body["policy_reason"] == "All policy checks passed"

    def test_deny_policy_reason_in_response(self, client):
        seed_tool(client, required_role="admin")
        seed_agent(client)
        seed_user(client, roles=["cs_agent"])
        body = _invoke(client).json()
        assert "lacks required role" in body["policy_reason"]

    def test_require_approval_policy_reason(self, client):
        _setup(client, risk_level="HIGH", approval_required=True)
        body = _invoke(client).json()
        assert "approval" in body["policy_reason"].lower()

    def test_policy_reason_in_audit_log(self, client):
        _setup(client, risk_level="LOW")
        request_id = _invoke(client).json()["request_id"]
        audit = client.get(f"/api/v1/audit-logs/{request_id}").json()
        assert audit["policy_reason"] == "All policy checks passed"


class TestDurationMs:
    def test_duration_ms_populated_after_execution(self, client):
        _setup(client, risk_level="LOW")
        body = _invoke(client).json()
        assert body["duration_ms"] is not None
        assert isinstance(body["duration_ms"], int)
        assert body["duration_ms"] >= 0

    def test_duration_ms_none_for_pending(self, client):
        _setup(client, risk_level="HIGH", approval_required=True)
        body = _invoke(client).json()
        assert body["duration_ms"] is None

    def test_duration_ms_populated_after_approved_execute(self, client):
        _setup(client, risk_level="HIGH", approval_required=True)
        request_id = _invoke(client).json()["request_id"]
        approval_id = client.get("/api/v1/approvals?pending_only=true").json()[0]["approval_id"]
        client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver_id": "admin-001"})
        body = client.post(f"/api/v1/gateway/execute/{request_id}").json()
        assert body["duration_ms"] is not None
        assert body["duration_ms"] >= 0


class TestApprovalExecutedState:
    def test_approval_status_executed_after_execution(self, client):
        _setup(client, risk_level="HIGH", approval_required=True)
        request_id = _invoke(client).json()["request_id"]
        approval_id = client.get("/api/v1/approvals?pending_only=true").json()[0]["approval_id"]
        client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver_id": "admin-001"})
        body = client.post(f"/api/v1/gateway/execute/{request_id}").json()
        assert body["approval_status"] == "EXECUTED"

    def test_approval_status_not_executed_for_denied(self, client):
        seed_tool(client, required_role="admin")
        seed_agent(client)
        seed_user(client, roles=["cs_agent"])
        body = _invoke(client).json()
        assert body["approval_status"] is None


class TestAuditLogPagination:
    def test_empty_page(self, client):
        page = client.get("/api/v1/audit-logs").json()
        assert page["items"] == []
        assert page["total"] == 0
        assert page["has_next"] is False

    def test_page_metadata(self, client):
        _setup(client, risk_level="LOW")
        _invoke(client)
        page = client.get("/api/v1/audit-logs?limit=10&offset=0").json()
        assert page["total"] == 1
        assert page["limit"] == 10
        assert page["offset"] == 0
        assert page["has_next"] is False
        assert len(page["items"]) == 1

    def test_has_next_when_more_items(self, client):
        _setup(client, risk_level="LOW")
        _invoke(client)
        _invoke(client)  # second call (same tool)
        page = client.get("/api/v1/audit-logs?limit=1&offset=0").json()
        assert page["total"] == 2
        assert page["has_next"] is True
        assert len(page["items"]) == 1


class TestErrorResponseFormat:
    def test_not_found_returns_error_code(self, client):
        resp = client.get("/api/v1/tools/nonexistent-tool")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "NOT_FOUND"
        assert "message" in body

    def test_unknown_tool_invoke_returns_404(self, client):
        seed_agent(client)
        seed_user(client)
        resp = client.post("/api/v1/gateway/invoke", json={
            "agent_id": "cs-agent-001",
            "user_id": "user-001",
            "tool_name": "no_such_tool",
            "input": {},
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_domain_error_returns_422_with_code(self, client):
        _setup(client, risk_level="HIGH", approval_required=True)
        request_id = _invoke(client).json()["request_id"]
        resp = client.post(f"/api/v1/gateway/execute/{request_id}")
        assert resp.status_code == 422
        assert resp.json()["code"] == "DOMAIN_ERROR"

    def test_duplicate_tool_returns_409_with_code(self, client):
        seed_tool(client)
        resp = client.post("/api/v1/tools", json={
            "tool_id": "tool-refund",
            "name": "refund_order",
            "description": "dup",
            "domain": "order",
            "risk_level": "HIGH",
            "required_role": "cs_agent",
            "approval_required": True,
            "sandbox_supported": False,
            "daily_cost_limit": 100.0,
        })
        assert resp.status_code == 409
        assert resp.json()["code"] == "CONFLICT"
