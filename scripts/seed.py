"""
Demo seed: registers 4 tools, 1 agent, 1 user via the running API.
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
    with httpx.Client(base_url=BASE) as c:
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
        })
        print(f"[+] Agent: {r.status_code}")

        r = c.post("/users", json={
            "user_id": "user-001",
            "roles": ["cs_agent"],
        })
        print(f"[+] User: {r.status_code}")

    print("\nSeed complete. Open http://localhost:8000/docs")


if __name__ == "__main__":
    main()
