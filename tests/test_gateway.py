from tests.conftest import seed_agent, seed_tool, seed_user


def _invoke(client, tool_name="refund_order", **kwargs):
    payload = {
        "agent_id": "cs-agent-001",
        "user_id": "user-001",
        "tool_name": tool_name,
        "input": {"order_id": "ORDER-1234", "amount": 12000, "reason": "customer request"},
        **kwargs,
    }
    return client.post("/api/v1/gateway/invoke", json=payload)


def _setup(client, risk_level="LOW", approval_required=False):
    seed_tool(client, risk_level=risk_level, approval_required=approval_required)
    seed_agent(client)
    seed_user(client)


def test_invoke_allow(client):
    _setup(client, risk_level="LOW")
    body = _invoke(client).json()
    assert body["policy_decision"] == "ALLOW"
    assert body["execution_status"] == "SIMULATED"


def test_invoke_require_approval(client):
    _setup(client, risk_level="HIGH", approval_required=True)
    body = _invoke(client).json()
    assert body["policy_decision"] == "REQUIRE_APPROVAL"
    assert body["approval_status"] == "PENDING"
    assert body["execution_status"] is None


def test_invoke_deny_missing_role(client):
    seed_tool(client, required_role="admin")
    seed_agent(client)
    seed_user(client, roles=["cs_agent"])
    body = _invoke(client).json()
    assert body["policy_decision"] == "DENY"
    assert body["execution_status"] == "SKIPPED"


def test_invoke_deny_disabled_tool(client):
    seed_tool(client, risk_level="LOW")
    seed_agent(client)
    seed_user(client)
    client.patch("/api/v1/tools/tool-refund", json={"enabled": False})
    assert _invoke(client).json()["policy_decision"] == "DENY"


def test_invoke_unknown_tool(client):
    seed_agent(client)
    seed_user(client)
    assert _invoke(client, tool_name="nonexistent_tool").status_code == 404


def test_full_approval_flow(client):
    _setup(client, risk_level="HIGH", approval_required=True)

    # 1. invoke → PENDING
    body = _invoke(client).json()
    assert body["approval_status"] == "PENDING"
    request_id = body["request_id"]

    # 2. list approvals → get approval_id
    approvals = client.get("/api/v1/approvals?pending_only=true").json()
    assert len(approvals) == 1
    approval_id = approvals[0]["approval_id"]

    # 3. approve
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approver_id": "admin-001", "reason": "looks good"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    # 4. execute
    executed = client.post(f"/api/v1/gateway/execute/{request_id}")
    assert executed.status_code == 200
    assert executed.json()["execution_status"] == "SIMULATED"


def test_execute_without_approval_is_blocked(client):
    """Pending approval → execute must fail before approving."""
    _setup(client, risk_level="HIGH", approval_required=True)
    request_id = _invoke(client).json()["request_id"]
    resp = client.post(f"/api/v1/gateway/execute/{request_id}")
    assert resp.status_code == 422


def test_execute_after_rejection_is_blocked(client):
    """Rejected approval → execute must fail."""
    _setup(client, risk_level="HIGH", approval_required=True)
    body = _invoke(client).json()
    request_id = body["request_id"]
    approval_id = client.get("/api/v1/approvals").json()[0]["approval_id"]
    client.post(f"/api/v1/approvals/{approval_id}/reject", json={"approver_id": "admin-001"})
    resp = client.post(f"/api/v1/gateway/execute/{request_id}")
    assert resp.status_code == 422


def test_audit_log_created(client):
    _setup(client, risk_level="LOW")
    _invoke(client)
    page = client.get("/api/v1/audit-logs").json()
    assert page["total"] == 1
    assert page["items"][0]["tool_name"] == "refund_order"


def test_audit_log_detail_by_request_id(client):
    _setup(client, risk_level="LOW")
    request_id = _invoke(client).json()["request_id"]
    resp = client.get(f"/api/v1/audit-logs/{request_id}")
    assert resp.status_code == 200
    assert resp.json()["request_id"] == request_id
