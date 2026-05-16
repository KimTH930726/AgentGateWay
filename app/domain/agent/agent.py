from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Agent:
    agent_id: str
    name: str
    allowed_domains: List[str]
    enabled: bool
    # Governance budgets — optional, None means no limit
    daily_cost_limit: Optional[float] = None
    monthly_cost_limit: Optional[float] = None
    daily_token_limit: Optional[int] = None
    # Soft threshold absolute value; usage >= warn but < hard → REQUIRE_APPROVAL
    daily_cost_warn_threshold: Optional[float] = None

    def can_access_domain(self, domain: str) -> bool:
        return domain in self.allowed_domains
