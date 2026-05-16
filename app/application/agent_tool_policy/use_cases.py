"""
Agent Tool Policy use cases.

Every write (create/update/delete) is journaled to the ConfigChangeLog so the
governance feed can show "who flipped what on cs-agent, when, why" without
scraping repositories one by one.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.agent.repository import IAgentRepository
from app.domain.agent_tool_policy.agent_tool_policy import AgentToolPolicy
from app.domain.agent_tool_policy.repository import IAgentToolPolicyRepository
from app.domain.enums import AgentToolPolicyType, ChangeType, GovernanceEntityType
from app.domain.governance.change_log import ConfigChangeLog
from app.domain.governance.repository import IConfigChangeLogRepository
from app.domain.shared.exceptions import ConflictError, NotFoundError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot(policy: AgentToolPolicy) -> dict:
    return {
        "policy_id": policy.policy_id,
        "agent_id": policy.agent_id,
        "tool_name": policy.tool_name,
        "policy_type": policy.policy_type.value,
        "enabled": policy.enabled,
        "reason": policy.reason,
        "created_by": policy.created_by,
    }


def _journal(
    log_repo: IConfigChangeLogRepository,
    *,
    change_type: ChangeType,
    entity_key: str,
    before: Optional[dict],
    after: Optional[dict],
    reason: str,
    changed_by: str,
) -> None:
    log_repo.append(
        ConfigChangeLog(
            log_id=str(uuid.uuid4()),
            entity_type=GovernanceEntityType.AGENT_TOOL_POLICY,
            entity_key=entity_key,
            change_type=change_type,
            before=before,
            after=after,
            reason=reason,
            changed_by=changed_by,
            changed_at=_now(),
        )
    )


@dataclass(frozen=True)
class CreateAgentToolPolicyCommand:
    agent_id: str
    tool_name: str
    policy_type: AgentToolPolicyType
    reason: str = ""
    created_by: str = ""


class CreateAgentToolPolicyUseCase:
    def __init__(
        self,
        repo: IAgentToolPolicyRepository,
        agent_repo: IAgentRepository,
        log_repo: IConfigChangeLogRepository,
    ) -> None:
        self._repo = repo
        self._agent_repo = agent_repo
        self._log_repo = log_repo

    def execute(self, cmd: CreateAgentToolPolicyCommand) -> AgentToolPolicy:
        if not self._agent_repo.find_by_agent_id(cmd.agent_id):
            raise NotFoundError(f"Agent not registered: {cmd.agent_id}")

        # Pre-check duplicate to surface a clean 409 ahead of the DB unique
        # constraint trip. The repo's IntegrityError handler is still the
        # ultimate guarantor for concurrent writers.
        for existing in self._repo.find_by_agent(cmd.agent_id):
            if existing.tool_name == cmd.tool_name and existing.policy_type == cmd.policy_type:
                raise ConflictError(
                    f"AgentToolPolicy already exists: agent={cmd.agent_id}, "
                    f"tool={cmd.tool_name}, type={cmd.policy_type.value}"
                )

        policy = AgentToolPolicy(
            policy_id=str(uuid.uuid4()),
            agent_id=cmd.agent_id,
            tool_name=cmd.tool_name,
            policy_type=cmd.policy_type,
            enabled=True,
            reason=cmd.reason,
            created_by=cmd.created_by,
            created_at=_now(),
        )
        saved = self._repo.save(policy)
        _journal(
            self._log_repo,
            change_type=ChangeType.CREATE,
            entity_key=saved.policy_id,
            before=None,
            after=_snapshot(saved),
            reason=cmd.reason,
            changed_by=cmd.created_by,
        )
        return saved


class ListAgentToolPoliciesUseCase:
    def __init__(self, repo: IAgentToolPolicyRepository) -> None:
        self._repo = repo

    def execute(self, agent_id: Optional[str] = None) -> List[AgentToolPolicy]:
        if agent_id:
            return self._repo.find_by_agent(agent_id)
        return self._repo.find_all()


class GetAgentToolPolicyUseCase:
    def __init__(self, repo: IAgentToolPolicyRepository) -> None:
        self._repo = repo

    def execute(self, policy_id: str) -> AgentToolPolicy:
        policy = self._repo.find_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"AgentToolPolicy not found: {policy_id}")
        return policy


@dataclass(frozen=True)
class UpdateAgentToolPolicyCommand:
    policy_id: str
    enabled: Optional[bool] = None
    reason: Optional[str] = None
    changed_by: str = ""
    change_reason: str = ""


class UpdateAgentToolPolicyUseCase:
    def __init__(
        self,
        repo: IAgentToolPolicyRepository,
        log_repo: IConfigChangeLogRepository,
    ) -> None:
        self._repo = repo
        self._log_repo = log_repo

    def execute(self, cmd: UpdateAgentToolPolicyCommand) -> AgentToolPolicy:
        existing = self._repo.find_by_id(cmd.policy_id)
        if not existing:
            raise NotFoundError(f"AgentToolPolicy not found: {cmd.policy_id}")

        updates: dict = {}
        if cmd.enabled is not None:
            updates["enabled"] = cmd.enabled
        if cmd.reason is not None:
            updates["reason"] = cmd.reason
        if not updates:
            return existing

        updated = self._repo.update(cmd.policy_id, updates)
        if not updated:
            raise NotFoundError(f"AgentToolPolicy not found: {cmd.policy_id}")

        _journal(
            self._log_repo,
            change_type=ChangeType.UPDATE,
            entity_key=updated.policy_id,
            before=_snapshot(existing),
            after=_snapshot(updated),
            reason=cmd.change_reason,
            changed_by=cmd.changed_by,
        )
        return updated


@dataclass(frozen=True)
class DeleteAgentToolPolicyCommand:
    policy_id: str
    changed_by: str = ""
    change_reason: str = ""


class DeleteAgentToolPolicyUseCase:
    def __init__(
        self,
        repo: IAgentToolPolicyRepository,
        log_repo: IConfigChangeLogRepository,
    ) -> None:
        self._repo = repo
        self._log_repo = log_repo

    def execute(self, cmd: DeleteAgentToolPolicyCommand) -> None:
        existing = self._repo.find_by_id(cmd.policy_id)
        if not existing:
            raise NotFoundError(f"AgentToolPolicy not found: {cmd.policy_id}")
        if not self._repo.delete(cmd.policy_id):
            raise NotFoundError(f"AgentToolPolicy not found: {cmd.policy_id}")
        _journal(
            self._log_repo,
            change_type=ChangeType.DELETE,
            entity_key=existing.policy_id,
            before=_snapshot(existing),
            after=None,
            reason=cmd.change_reason,
            changed_by=cmd.changed_by,
        )
