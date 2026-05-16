"""
AgentToolPolicy — per-agent allowlist / denylist entry.

Semantics (evaluated by AgentToolPolicyRule, not by this aggregate itself):
  1. If any enabled DENY entry matches (agent_id, tool_name)        → DENY.
  2. Else if the agent has any enabled ALLOW entries at all and the
     tool is NOT in that allowlist                                  → DENY.
  3. Otherwise                                                       → fall through.

DENY beats ALLOW. The aggregate just carries the data; the rule applies the
precedence so the tested rule and stored entries stay decoupled.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from app.domain.enums import AgentToolPolicyType


@dataclass(frozen=True)
class AgentToolPolicy:
    policy_id: str
    agent_id: str
    tool_name: str
    policy_type: AgentToolPolicyType
    enabled: bool
    reason: str
    created_by: str
    created_at: datetime


def evaluate_agent_tool_policies(
    policies: Iterable[AgentToolPolicy],
    tool_name: str,
) -> "PolicyDecisionForTool":
    """Pure helper — returns the policy decision for a specific tool given an
    agent's policy set. Kept side-effect-free so it can be unit-tested in
    isolation and reused by both the policy rule and admin queries."""
    enabled = [p for p in policies if p.enabled]
    deny_match = any(
        p.tool_name == tool_name and p.policy_type == AgentToolPolicyType.DENY
        for p in enabled
    )
    if deny_match:
        return PolicyDecisionForTool.DENIED_BY_DENYLIST

    allow_entries: List[AgentToolPolicy] = [
        p for p in enabled if p.policy_type == AgentToolPolicyType.ALLOW
    ]
    if not allow_entries:
        return PolicyDecisionForTool.NO_OPINION

    if any(p.tool_name == tool_name for p in allow_entries):
        return PolicyDecisionForTool.ALLOWED_BY_ALLOWLIST
    return PolicyDecisionForTool.DENIED_BY_ALLOWLIST_OMISSION


from enum import Enum


class PolicyDecisionForTool(str, Enum):
    NO_OPINION = "NO_OPINION"
    ALLOWED_BY_ALLOWLIST = "ALLOWED_BY_ALLOWLIST"
    DENIED_BY_ALLOWLIST_OMISSION = "DENIED_BY_ALLOWLIST_OMISSION"
    DENIED_BY_DENYLIST = "DENIED_BY_DENYLIST"
