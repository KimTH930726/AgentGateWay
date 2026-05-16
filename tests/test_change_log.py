"""
Tests for the governance Config Change Log.
Tool edits and Agent Tool Policy edits should leave an immutable trail.
"""
from tests.conftest import seed_agent, seed_agent_tool_policy, seed_tool


def _all_logs(client, **params):
    return client.get("/api/v1/governance/change-logs", params=params).json()


class TestToolChangeLog:
    def test_create_tool_writes_log(self, client):
        seed_tool(client)
        page = _all_logs(client, entity_type="TOOL")
        assert page["total"] >= 1
        entry = page["items"][0]
        assert entry["entity_type"] == "TOOL"
        assert entry["change_type"] == "CREATE"
        assert entry["entity_key"] == "tool-refund"
        assert entry["after"]["name"] == "refund_order"

    def test_update_tool_writes_before_after(self, client):
        seed_tool(client)
        client.patch(
            "/api/v1/tools/tool-refund",
            json={"enabled": False},
            headers={"X-Acting-User": "admin-9", "X-Change-Reason": "incident response"},
        )
        page = _all_logs(client, entity_type="TOOL")
        update_entry = next(e for e in page["items"] if e["change_type"] == "UPDATE")
        assert update_entry["before"]["enabled"] is True
        assert update_entry["after"]["enabled"] is False
        assert update_entry["changed_by"] == "admin-9"
        assert update_entry["reason"] == "incident response"

    def test_delete_tool_writes_log(self, client):
        seed_tool(client)
        client.delete(
            "/api/v1/tools/tool-refund",
            headers={"X-Acting-User": "admin-7"},
        )
        page = _all_logs(client, entity_type="TOOL")
        delete_entry = next(e for e in page["items"] if e["change_type"] == "DELETE")
        assert delete_entry["before"]["tool_id"] == "tool-refund"
        assert delete_entry["after"] is None
        assert delete_entry["changed_by"] == "admin-7"


class TestAgentToolPolicyChangeLog:
    def test_policy_create_logs_after_state(self, client):
        seed_agent(client)
        created = seed_agent_tool_policy(
            client, tool_name="delete_user", policy_type="DENY",
            reason="destructive", created_by="admin-1",
        )
        page = _all_logs(client, entity_type="AGENT_TOOL_POLICY")
        entry = page["items"][0]
        assert entry["entity_key"] == created["policy_id"]
        assert entry["after"]["policy_type"] == "DENY"
        assert entry["after"]["tool_name"] == "delete_user"
        assert entry["changed_by"] == "admin-1"

    def test_policy_update_logs_before_after(self, client):
        seed_agent(client)
        created = seed_agent_tool_policy(
            client, tool_name="delete_user", policy_type="DENY",
        )
        client.patch(
            f"/api/v1/agent-tool-policies/{created['policy_id']}",
            json={"enabled": False, "change_reason": "tool retired", "changed_by": "admin-2"},
        )
        page = _all_logs(
            client, entity_type="AGENT_TOOL_POLICY",
            entity_key=created["policy_id"],
        )
        update = next(e for e in page["items"] if e["change_type"] == "UPDATE")
        assert update["before"]["enabled"] is True
        assert update["after"]["enabled"] is False
        assert update["reason"] == "tool retired"

    def test_policy_delete_logs_before(self, client):
        seed_agent(client)
        created = seed_agent_tool_policy(
            client, tool_name="delete_user", policy_type="DENY",
        )
        client.request(
            "DELETE",
            f"/api/v1/agent-tool-policies/{created['policy_id']}",
            json={"changed_by": "admin-3", "change_reason": "obsolete"},
        )
        page = _all_logs(
            client, entity_type="AGENT_TOOL_POLICY",
            entity_key=created["policy_id"],
        )
        delete = next(e for e in page["items"] if e["change_type"] == "DELETE")
        assert delete["before"]["policy_id"] == created["policy_id"]
        assert delete["after"] is None
        assert delete["changed_by"] == "admin-3"


class TestChangeLogPagination:
    def test_filter_by_entity_type(self, client):
        seed_tool(client)
        seed_agent(client)
        seed_agent_tool_policy(client, tool_name="delete_user", policy_type="DENY")
        tools_page = _all_logs(client, entity_type="TOOL")
        policies_page = _all_logs(client, entity_type="AGENT_TOOL_POLICY")
        assert all(e["entity_type"] == "TOOL" for e in tools_page["items"])
        assert all(e["entity_type"] == "AGENT_TOOL_POLICY" for e in policies_page["items"])

    def test_pagination_metadata(self, client):
        # Two tool entries → two log rows
        seed_tool(client, tool_id="t1", name="get_order_detail")
        seed_tool(client, tool_id="t2", name="cancel_order")
        page = _all_logs(client, limit=1, offset=0, entity_type="TOOL")
        assert page["total"] == 2
        assert page["limit"] == 1
        assert page["has_next"] is True
        assert len(page["items"]) == 1
