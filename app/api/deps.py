from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.agent_tool_policy.use_cases import (
    CreateAgentToolPolicyUseCase, DeleteAgentToolPolicyUseCase,
    GetAgentToolPolicyUseCase, ListAgentToolPoliciesUseCase,
    UpdateAgentToolPolicyUseCase,
)
from app.application.approval.use_cases import (
    ApproveToolCallUseCase, GetApprovalUseCase,
    ListApprovalsUseCase, RejectToolCallUseCase,
)
from app.application.gateway.use_cases import ExecuteApprovedUseCase, InvokeToolUseCase
from app.application.governance.use_cases import ListChangeLogsUseCase
from app.application.tool.use_cases import (
    DeleteToolUseCase, GetToolUseCase, ListToolsUseCase,
    RegisterToolUseCase, UpdateToolUseCase,
)
from app.domain.policy.policy_engine import PolicyEngine
from app.infrastructure.execution.mock_executor import MockExecutor
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.agent_repository import AgentRepository
from app.infrastructure.persistence.repositories.agent_tool_policy_repository import (
    AgentToolPolicyRepository,
)
from app.infrastructure.persistence.repositories.change_log_repository import (
    ConfigChangeLogRepository,
)
from app.infrastructure.persistence.repositories.tool_call_repository import ToolCallRepository
from app.infrastructure.persistence.repositories.tool_repository import ToolRepository
from app.infrastructure.persistence.repositories.user_repository import UserRepository


# --- primitive repos (needed by agent/user routers) -----------------------

def get_agent_repo(db: Session = Depends(get_db)) -> AgentRepository:
    return AgentRepository(db)


def get_user_repo(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_tool_call_repo(db: Session = Depends(get_db)) -> ToolCallRepository:
    return ToolCallRepository(db)


def get_change_log_repo(db: Session = Depends(get_db)) -> ConfigChangeLogRepository:
    return ConfigChangeLogRepository(db)


def get_agent_tool_policy_repo(
    db: Session = Depends(get_db),
) -> AgentToolPolicyRepository:
    return AgentToolPolicyRepository(db)


# --- tool use cases -------------------------------------------------------

def get_register_tool(db: Session = Depends(get_db)) -> RegisterToolUseCase:
    return RegisterToolUseCase(ToolRepository(db), ConfigChangeLogRepository(db))


def get_get_tool(db: Session = Depends(get_db)) -> GetToolUseCase:
    return GetToolUseCase(ToolRepository(db))


def get_list_tools(db: Session = Depends(get_db)) -> ListToolsUseCase:
    return ListToolsUseCase(ToolRepository(db))


def get_update_tool(db: Session = Depends(get_db)) -> UpdateToolUseCase:
    return UpdateToolUseCase(ToolRepository(db), ConfigChangeLogRepository(db))


def get_delete_tool(db: Session = Depends(get_db)) -> DeleteToolUseCase:
    return DeleteToolUseCase(ToolRepository(db), ConfigChangeLogRepository(db))


# --- gateway use cases ----------------------------------------------------

def get_invoke_tool(db: Session = Depends(get_db)) -> InvokeToolUseCase:
    return InvokeToolUseCase(
        tool_repo=ToolRepository(db),
        agent_repo=AgentRepository(db),
        user_repo=UserRepository(db),
        tool_call_repo=ToolCallRepository(db),
        policy_engine=PolicyEngine(),
        executor=MockExecutor(),
        agent_tool_policy_repo=AgentToolPolicyRepository(db),
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


# --- agent tool policy use cases -----------------------------------------

def get_create_agent_tool_policy(
    db: Session = Depends(get_db),
) -> CreateAgentToolPolicyUseCase:
    return CreateAgentToolPolicyUseCase(
        repo=AgentToolPolicyRepository(db),
        agent_repo=AgentRepository(db),
        log_repo=ConfigChangeLogRepository(db),
    )


def get_list_agent_tool_policies(
    db: Session = Depends(get_db),
) -> ListAgentToolPoliciesUseCase:
    return ListAgentToolPoliciesUseCase(AgentToolPolicyRepository(db))


def get_get_agent_tool_policy(
    db: Session = Depends(get_db),
) -> GetAgentToolPolicyUseCase:
    return GetAgentToolPolicyUseCase(AgentToolPolicyRepository(db))


def get_update_agent_tool_policy(
    db: Session = Depends(get_db),
) -> UpdateAgentToolPolicyUseCase:
    return UpdateAgentToolPolicyUseCase(
        repo=AgentToolPolicyRepository(db),
        log_repo=ConfigChangeLogRepository(db),
    )


def get_delete_agent_tool_policy(
    db: Session = Depends(get_db),
) -> DeleteAgentToolPolicyUseCase:
    return DeleteAgentToolPolicyUseCase(
        repo=AgentToolPolicyRepository(db),
        log_repo=ConfigChangeLogRepository(db),
    )


# --- governance use cases ------------------------------------------------

def get_list_change_logs(db: Session = Depends(get_db)) -> ListChangeLogsUseCase:
    return ListChangeLogsUseCase(ConfigChangeLogRepository(db))
