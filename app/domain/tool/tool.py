from dataclasses import dataclass
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

    def requires_approval(self) -> bool:
        return self.approval_required or self.risk_level == RiskLevel.HIGH
