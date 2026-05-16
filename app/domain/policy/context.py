from dataclasses import dataclass, field
from typing import List, Optional

from app.domain.agent.agent import Agent
from app.domain.agent_tool_policy.agent_tool_policy import AgentToolPolicy
from app.domain.enums import PolicyDecision
from app.domain.policy.trace import RuleEvaluation
from app.domain.tool.tool import Tool
from app.domain.user.user import User


@dataclass(frozen=True)
class PolicyContext:
    tool: Tool
    agent: Agent
    user: User
    daily_usage_cost: float
    # Aggregated daily/monthly spend across all tools for the agent.
    # Optional so callers that don't track agent-level budgets can pass None
    # without forcing the AgentBudgetRule to fire incorrectly.
    agent_daily_cost: Optional[float] = None
    agent_monthly_cost: Optional[float] = None
    agent_daily_tokens: Optional[int] = None
    # Per-agent policy entries — empty list means "no opinion".
    agent_tool_policies: List[AgentToolPolicy] = field(default_factory=list)


@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str
    trace: List[RuleEvaluation] = field(default_factory=list)
