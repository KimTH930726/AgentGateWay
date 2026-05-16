"""
Demo seed: registers tools, an agent with a daily budget, a user,
and a couple of AgentToolPolicy entries that exercise the governance
extension (allowlist + denylist).

Run: python scripts/seed.py
"""
import httpx

BASE = "http://localhost:8000/api/v1"

TOOLS = [
    {
        "tool_id": "tool-refund-order",
        "name": "refund_order",
        "description": "고객 주문에 대해 환불을 처리합니다.",
        "domain": "order",
        "risk_level": "HIGH",
        "required_role": "cs_agent",
        "approval_required": True,
        "sandbox_supported": True,
        "daily_cost_limit": 5000.0,
        "warn_cost_threshold": 4000.0,
    },
    {
        "tool_id": "tool-get-order",
        "name": "get_order_detail",
        "description": "주문 상세 정보를 조회합니다.",
        "domain": "order",
        "risk_level": "LOW",
        "required_role": "cs_agent",
        "approval_required": False,
        "sandbox_supported": True,
        "daily_cost_limit": 10000.0,
    },
    {
        "tool_id": "tool-cancel-order",
        "name": "cancel_order",
        "description": "주문을 취소합니다.",
        "domain": "order",
        "risk_level": "MEDIUM",
        "required_role": "cs_agent",
        "approval_required": False,
        "sandbox_supported": True,
        "daily_cost_limit": 2000.0,
    },
    {
        "tool_id": "tool-send-coupon",
        "name": "send_coupon",
        "description": "고객에게 쿠폰을 발송합니다.",
        "domain": "marketing",
        "risk_level": "LOW",
        "required_role": "cs_agent",
        "approval_required": False,
        "sandbox_supported": True,
        "daily_cost_limit": 500.0,
    },
]


def main():
    headers = {"X-Acting-User": "seed-script", "X-Change-Reason": "initial seed"}
    with httpx.Client(base_url=BASE, headers=headers) as c:
        for tool in TOOLS:
            r = c.post("/tools", json=tool)
            if r.status_code == 201:
                print(f"[+] Tool created: {tool['name']}")
            elif r.status_code == 409:
                print(f"[=] Tool exists:  {tool['name']}")
            else:
                print(f"[!] Error {r.status_code}: {r.text}")

        r = c.post("/agents", json={
            "agent_id": "cs-agent-001",
            "name": "Customer Service Agent",
            "allowed_domains": ["order", "marketing"],
            "daily_cost_limit": 20.0,
            "daily_cost_warn_threshold": 15.0,
            "daily_token_limit": 1_000_000,
        })
        print(f"[+] Agent: {r.status_code}")

        r = c.post("/users", json={
            "user_id": "user-001",
            "roles": ["cs_agent"],
        })
        print(f"[+] User: {r.status_code}")

        # Governance policies — block a destructive tool for this agent,
        # explicitly allow a safe one.
        for policy in [
            {"tool_name": "delete_user", "policy_type": "DENY",
             "reason": "destructive — never let CS agents delete users"},
            {"tool_name": "send_coupon", "policy_type": "ALLOW",
             "reason": "explicit allowlist entry for promo flows"},
        ]:
            r = c.post("/agent-tool-policies", json={
                "agent_id": "cs-agent-001",
                "created_by": "seed-script",
                **policy,
            })
            print(f"[+] AgentToolPolicy {policy['policy_type']} {policy['tool_name']}: {r.status_code}")

    print("\nSeed complete. Open http://localhost:8000/docs")


if __name__ == "__main__":
    main()
