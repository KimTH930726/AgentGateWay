from tests.conftest import seed_tool


def test_register_tool(client):
    tool = seed_tool(client)
    assert tool["tool_id"] == "tool-refund"
    assert tool["risk_level"] == "HIGH"
    assert tool["enabled"] is True


def test_register_duplicate_tool(client):
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


def test_list_tools(client):
    seed_tool(client, tool_id="t1", name="refund_order")
    seed_tool(client, tool_id="t2", name="get_order_detail")
    resp = client.get("/api/v1/tools")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_tool(client):
    seed_tool(client)
    resp = client.get("/api/v1/tools/tool-refund")
    assert resp.status_code == 200
    assert resp.json()["name"] == "refund_order"


def test_get_tool_not_found(client):
    resp = client.get("/api/v1/tools/nonexistent")
    assert resp.status_code == 404


def test_update_tool(client):
    seed_tool(client)
    resp = client.patch("/api/v1/tools/tool-refund", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_delete_tool(client):
    seed_tool(client)
    resp = client.delete("/api/v1/tools/tool-refund")
    assert resp.status_code == 204
    assert client.get("/api/v1/tools/tool-refund").status_code == 404
