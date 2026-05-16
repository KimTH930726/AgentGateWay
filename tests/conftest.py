import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.persistence.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- Seed helpers ---------------------------------------------------------

def seed_tool(
    client,
    *,
    tool_id="tool-refund",
    name="refund_order",
    risk_level="HIGH",
    approval_required=True,
    domain="order",
    required_role="cs_agent",
    daily_cost_limit=1000.0,
):
    resp = client.post("/api/v1/tools", json={
        "tool_id": tool_id,
        "name": name,
        "description": "환불 처리 도구",
        "domain": domain,
        "risk_level": risk_level,
        "required_role": required_role,
        "approval_required": approval_required,
        "sandbox_supported": True,
        "daily_cost_limit": daily_cost_limit,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def seed_agent(
    client,
    *,
    agent_id="cs-agent-001",
    domains=None,
    daily_cost_limit=None,
    daily_cost_warn_threshold=None,
    daily_token_limit=None,
):
    payload = {
        "agent_id": agent_id,
        "name": "CS Agent",
        "allowed_domains": domains or ["order"],
    }
    if daily_cost_limit is not None:
        payload["daily_cost_limit"] = daily_cost_limit
    if daily_cost_warn_threshold is not None:
        payload["daily_cost_warn_threshold"] = daily_cost_warn_threshold
    if daily_token_limit is not None:
        payload["daily_token_limit"] = daily_token_limit
    resp = client.post("/api/v1/agents", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def seed_agent_tool_policy(
    client,
    *,
    agent_id="cs-agent-001",
    tool_name="refund_order",
    policy_type="DENY",
    reason="",
    created_by="admin-001",
):
    resp = client.post("/api/v1/agent-tool-policies", json={
        "agent_id": agent_id,
        "tool_name": tool_name,
        "policy_type": policy_type,
        "reason": reason,
        "created_by": created_by,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def seed_user(client, *, user_id="user-001", roles=None):
    resp = client.post("/api/v1/users", json={
        "user_id": user_id,
        "roles": roles or ["cs_agent"],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()
