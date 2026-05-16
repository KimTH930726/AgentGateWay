from dataclasses import dataclass
from typing import Optional

from app.domain.enums import RiskLevel


@dataclass(frozen=True)
class Tool:
    tool_id: str
    name: str
    description: str
    domain: str
    risk_level: RiskLevel
    required_role: str
    approval_required: bool
    sandbox_supported: bool
    daily_cost_limit: float
    enabled: bool
    # Soft cost threshold (absolute). When daily_usage_cost >= threshold but
    # < daily_cost_limit, the call is escalated to REQUIRE_APPROVAL instead
    # of being denied outright. None disables the soft check.
    warn_cost_threshold: Optional[float] = None

    def requires_approval(self) -> bool:
        return self.approval_required or self.risk_level == RiskLevel.HIGH
