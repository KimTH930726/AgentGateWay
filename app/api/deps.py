from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.agent_repository import AgentRepository
from app.infrastructure.persistence.repositories.tool_repository import ToolRepository
from app.infrastructure.persistence.repositories.tool_call_repository import ToolCallRepository
from app.infrastructure.persistence.repositories.user_repository import UserRepository
from app.infrastructure.execution.mock_executor import MockExecutor
from app.domain.policy.policy_engine import PolicyEngine
from app.application.tool.use_cases import (
    RegisterToolUseCase, GetToolUseCase, ListToolsUseCase,
    UpdateToolUseCase, DeleteToolUseCase,
)
from app.application.gateway.use_cases import InvokeToolUseCase, ExecuteApprovedUseCase
from app.application.approval.use_cases import (
    ListApprovalsUseCase, GetApprovalUseCase,
    ApproveToolCallUseCase, RejectToolCallUseCase,
)


# --- primitive repos (needed by agent/user routers) -----------------------

def get_agent_repo(db: Session = Depends(get_db)) -> AgentRepository:
    return AgentRepository(db)


def get_user_repo(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_tool_call_repo(db: Session = Depends(get_db)) -> ToolCallRepository:
    return ToolCallRepository(db)


# --- tool use cases -------------------------------------------------------

def get_register_tool(db: Session = Depends(get_db)) -> RegisterToolUseCase:
    return RegisterToolUseCase(ToolRepository(db))


def get_get_tool(db: Session = Depends(get_db)) -> GetToolUseCase:
    return GetToolUseCase(ToolRepository(db))


def get_list_tools(db: Session = Depends(get_db)) -> ListToolsUseCase:
    return ListToolsUseCase(ToolRepository(db))


def get_update_tool(db: Session = Depends(get_db)) -> UpdateToolUseCase:
    return UpdateToolUseCase(ToolRepository(db))


def get_delete_tool(db: Session = Depends(get_db)) -> DeleteToolUseCase:
    return DeleteToolUseCase(ToolRepository(db))


# --- gateway use cases ----------------------------------------------------

def get_invoke_tool(db: Session = Depends(get_db)) -> InvokeToolUseCase:
    return InvokeToolUseCase(
        tool_repo=ToolRepository(db),
        agent_repo=AgentRepository(db),
        user_repo=UserRepository(db),
        tool_call_repo=ToolCallRepository(db),
        policy_engine=PolicyEngine(),
        executor=MockExecutor(),
    )


def get_execute_approved(db: Session = Depends(get_db)) -> ExecuteApprovedUseCase:
    return ExecuteApprovedUseCase(
        tool_call_repo=ToolCallRepository(db),
        executor=MockExecutor(),
    )


# --- approval use cases ---------------------------------------------------

def get_list_approvals(db: Session = Depends(get_db)) -> ListApprovalsUseCase:
    return ListApprovalsUseCase(ToolCallRepository(db))


def get_get_approval(db: Session = Depends(get_db)) -> GetApprovalUseCase:
    return GetApprovalUseCase(ToolCallRepository(db))


def get_approve_tool_call(db: Session = Depends(get_db)) -> ApproveToolCallUseCase:
    return ApproveToolCallUseCase(ToolCallRepository(db))


def get_reject_tool_call(db: Session = Depends(get_db)) -> RejectToolCallUseCase:
    return RejectToolCallUseCase(ToolCallRepository(db))
