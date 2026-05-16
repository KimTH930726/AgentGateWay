"""
ConfigChangeLog — append-only record of every governance-relevant change.

Covers tool registry edits, agent budget changes, and AgentToolPolicy CRUD.
Stored separately from tool-call audit logs because the lifecycle (who edited
config, when, why) is orthogonal to per-call execution audit.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from app.domain.enums import ChangeType, GovernanceEntityType


@dataclass(frozen=True)
class ConfigChangeLog:
    log_id: str
    entity_type: GovernanceEntityType
    entity_key: str                 # human-readable identifier (tool_id, agent_id, policy_id, …)
    change_type: ChangeType
    before: Optional[Dict[str, Any]]
    after: Optional[Dict[str, Any]]
    reason: str
    changed_by: str
    changed_at: datetime
