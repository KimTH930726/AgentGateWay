from tests.conftest import seed_agent, seed_tool, seed_user


def _setup_and_invoke(client):
    seed_tool(client, risk_level="HIGH", approval_required=True)
    seed_agent(client)
    seed_user(client)
    resp = client.post("/api/v1/gateway/invoke", json={
        "agent_id": "cs-agent-001",
        "user_id": "user-001",
        "tool_name": "refund_order",
        "input": {"order_id": "ORDER-1234", "amount": 5000},
    })
    assert resp.status_code == 200
    return resp.json()["request_id"]


def test_list_all_approvals(client):
    _setup_and_invoke(client)
    resp = client.get("/api/v1/approvals")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_pending_approvals(client):
    _setup_and_invoke(client)
    resp = client.get("/api/v1/approvals?pending_only=true")
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "PENDING"


def test_approval_response_includes_tool_call_context(client):
    _setup_and_invoke(client)
    item = client.get("/api/v1/approvals").json()[0]
    assert "approval_id" in item
    assert "request_id" in item
    assert item["tool_name"] == "refund_order"
    assert item["risk_level"] == "HIGH"


def test_approve(client):
    _setup_and_invoke(client)
    approval_id = client.get("/api/v1/approvals").json()[0]["approval_id"]
    resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approver_id": "admin-001", "reason": "ok"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"
    assert resp.json()["approver_id"] == "admin-001"


def test_reject(client):
    _setup_and_invoke(client)
    approval_id = client.get("/api/v1/approvals").json()[0]["approval_id"]
    resp = client.post(
        f"/api/v1/approvals/{approval_id}/reject",
        json={"approver_id": "admin-001", "reason": "fraud risk"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


def test_double_approve_fails(client):
    _setup_and_invoke(client)
    approval_id = client.get("/api/v1/approvals").json()[0]["approval_id"]
    client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver_id": "admin-001"})
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver_id": "admin-002"})
    assert resp.status_code == 422
