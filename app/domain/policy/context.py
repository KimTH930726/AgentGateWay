from dataclasses import dataclass

from app.domain.agent.agent import Agent
from app.domain.enums import PolicyDecision
from app.domain.tool.tool import Tool
from app.domain.user.user import User


@dataclass(frozen=True)
class PolicyContext:
    tool: Tool
    agent: Agent
    user: User
    daily_usage_cost: float


@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str
