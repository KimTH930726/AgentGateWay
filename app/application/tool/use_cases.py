import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.enums import ChangeType, GovernanceEntityType, RiskLevel
from app.domain.governance.change_log import ConfigChangeLog
from app.domain.governance.repository import IConfigChangeLogRepository
from app.domain.shared.exceptions import NotFoundError
from app.domain.tool.repository import IToolRepository
from app.domain.tool.tool import Tool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tool_snapshot(tool: Tool) -> dict:
    return {
        "tool_id": tool.tool_id,
        "name": tool.name,
        "description": tool.description,
        "domain": tool.domain,
        "risk_level": tool.risk_level.value,
        "required_role": tool.required_role,
        "approval_required": tool.approval_required,
        "sandbox_supported": tool.sandbox_supported,
        "daily_cost_limit": tool.daily_cost_limit,
        "warn_cost_threshold": tool.warn_cost_threshold,
        "enabled": tool.enabled,
    }


def _journal(
    log_repo: Optional[IConfigChangeLogRepository],
    *,
    change_type: ChangeType,
    entity_key: str,
    before: Optional[dict],
    after: Optional[dict],
    reason: str,
    changed_by: str,
) -> None:
    if log_repo is None:
        return
    log_repo.append(
        ConfigChangeLog(
            log_id=str(uuid.uuid4()),
            entity_type=GovernanceEntityType.TOOL,
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
class RegisterToolCommand:
    tool_id: str
    name: str
    description: str
    domain: str
    risk_level: RiskLevel
    required_role: str
    approval_required: bool
    sandbox_supported: bool
    daily_cost_limit: float
    warn_cost_threshold: Optional[float] = None
    changed_by: str = ""
    change_reason: str = ""


class RegisterToolUseCase:
    def __init__(
        self,
        repo: IToolRepository,
        log_repo: Optional[IConfigChangeLogRepository] = None,
    ) -> None:
        self._repo = repo
        self._log_repo = log_repo

    def execute(self, cmd: RegisterToolCommand) -> Tool:
        if self._repo.find_by_tool_id(cmd.tool_id):
            raise ValueError(f"Tool already exists: {cmd.tool_id}")
        tool = Tool(
            tool_id=cmd.tool_id,
            name=cmd.name,
            description=cmd.description,
            domain=cmd.domain,
            risk_level=cmd.risk_level,
            required_role=cmd.required_role,
            approval_required=cmd.approval_required,
            sandbox_supported=cmd.sandbox_supported,
            daily_cost_limit=cmd.daily_cost_limit,
            enabled=True,
            warn_cost_threshold=cmd.warn_cost_threshold,
        )
        saved = self._repo.save(tool)
        _journal(
            self._log_repo,
            change_type=ChangeType.CREATE,
            entity_key=saved.tool_id,
            before=None,
            after=_tool_snapshot(saved),
            reason=cmd.change_reason,
            changed_by=cmd.changed_by,
        )
        return saved


class GetToolUseCase:
    def __init__(self, repo: IToolRepository) -> None:
        self._repo = repo

    def execute(self, tool_id: str) -> Tool:
        tool = self._repo.find_by_tool_id(tool_id)
        if not tool:
            raise NotFoundError(f"Tool not found: {tool_id}")
        return tool


class ListToolsUseCase:
    def __init__(self, repo: IToolRepository) -> None:
        self._repo = repo

    def execute(self) -> List[Tool]:
        return self._repo.find_all()


@dataclass(frozen=True)
class UpdateToolCommand:
    tool_id: str
    updates: dict
    changed_by: str = ""
    change_reason: str = ""


class UpdateToolUseCase:
    def __init__(
        self,
        repo: IToolRepository,
        log_repo: Optional[IConfigChangeLogRepository] = None,
    ) -> None:
        self._repo = repo
        self._log_repo = log_repo

    def execute(self, cmd: UpdateToolCommand) -> Tool:
        existing = self._repo.find_by_tool_id(cmd.tool_id)
        if not existing:
            raise NotFoundError(f"Tool not found: {cmd.tool_id}")
        tool = self._repo.update(cmd.tool_id, cmd.updates)
        if not tool:
            raise NotFoundError(f"Tool not found: {cmd.tool_id}")
        _journal(
            self._log_repo,
            change_type=ChangeType.UPDATE,
            entity_key=tool.tool_id,
            before=_tool_snapshot(existing),
            after=_tool_snapshot(tool),
            reason=cmd.change_reason,
            changed_by=cmd.changed_by,
        )
        return tool


@dataclass(frozen=True)
class DeleteToolCommand:
    tool_id: str
    changed_by: str = ""
    change_reason: str = ""


class DeleteToolUseCase:
    def __init__(
        self,
        repo: IToolRepository,
        log_repo: Optional[IConfigChangeLogRepository] = None,
    ) -> None:
        self._repo = repo
        self._log_repo = log_repo

    def execute(self, cmd) -> None:
        # Accept either the bare tool_id (backwards-compat) or a command DTO.
        if isinstance(cmd, str):
            cmd = DeleteToolCommand(tool_id=cmd)
        existing = self._repo.find_by_tool_id(cmd.tool_id)
        if not existing:
            raise NotFoundError(f"Tool not found: {cmd.tool_id}")
        if not self._repo.delete(cmd.tool_id):
            raise NotFoundError(f"Tool not found: {cmd.tool_id}")
        _journal(
            self._log_repo,
            change_type=ChangeType.DELETE,
            entity_key=cmd.tool_id,
            before=_tool_snapshot(existing),
            after=None,
            reason=cmd.change_reason,
            changed_by=cmd.changed_by,
        )
