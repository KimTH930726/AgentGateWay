from dataclasses import dataclass
from typing import List, Optional

from app.domain.shared.exceptions import NotFoundError
from app.domain.tool_call.repository import IToolCallRepository
from app.domain.tool_call.tool_call import ToolCall


@dataclass(frozen=True)
class ApproveCommand:
    approval_id: str
    approver_id: str
    reason: Optional[str]


@dataclass(frozen=True)
class RejectCommand:
    approval_id: str
    approver_id: str
    reason: Optional[str]


class ListApprovalsUseCase:
    def __init__(self, repo: IToolCallRepository) -> None:
        self._repo = repo

    def execute(self, pending_only: bool = False) -> List[ToolCall]:
        return self._repo.find_with_approvals(pending_only=pending_only)


class GetApprovalUseCase:
    def __init__(self, repo: IToolCallRepository) -> None:
        self._repo = repo

    def execute(self, approval_id: str) -> ToolCall:
        tool_call = self._repo.find_by_approval_id(approval_id)
        if not tool_call:
            raise NotFoundError(f"Approval not found: {approval_id}")
        return tool_call


class ApproveToolCallUseCase:
    def __init__(self, repo: IToolCallRepository) -> None:
        self._repo = repo

    def execute(self, cmd: ApproveCommand) -> ToolCall:
        tool_call = self._repo.find_by_approval_id(cmd.approval_id)
        if not tool_call:
            raise NotFoundError(f"Approval not found: {cmd.approval_id}")
        tool_call.approve(cmd.approver_id, cmd.reason)  # raises DomainError if not PENDING
        self._repo.save(tool_call)
        return tool_call


class RejectToolCallUseCase:
    def __init__(self, repo: IToolCallRepository) -> None:
        self._repo = repo

    def execute(self, cmd: RejectCommand) -> ToolCall:
        tool_call = self._repo.find_by_approval_id(cmd.approval_id)
        if not tool_call:
            raise NotFoundError(f"Approval not found: {cmd.approval_id}")
        tool_call.reject(cmd.approver_id, cmd.reason)
        self._repo.save(tool_call)
        return tool_call
