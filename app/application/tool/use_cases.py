from dataclasses import dataclass
from typing import List, Optional

from app.domain.enums import RiskLevel
from app.domain.shared.exceptions import NotFoundError
from app.domain.tool.repository import IToolRepository
from app.domain.tool.tool import Tool


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


class RegisterToolUseCase:
    def __init__(self, repo: IToolRepository) -> None:
        self._repo = repo

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
        )
        return self._repo.save(tool)


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


class UpdateToolUseCase:
    def __init__(self, repo: IToolRepository) -> None:
        self._repo = repo

    def execute(self, cmd: UpdateToolCommand) -> Tool:
        tool = self._repo.update(cmd.tool_id, cmd.updates)
        if not tool:
            raise NotFoundError(f"Tool not found: {cmd.tool_id}")
        return tool


class DeleteToolUseCase:
    def __init__(self, repo: IToolRepository) -> None:
        self._repo = repo

    def execute(self, tool_id: str) -> None:
        if not self._repo.delete(tool_id):
            raise NotFoundError(f"Tool not found: {tool_id}")
