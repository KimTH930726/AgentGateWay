from dataclasses import dataclass
from typing import Any, Dict

from app.domain.enums import PolicyDecision
from app.domain.policy.policy_engine import PolicyContext, PolicyEngine
from app.domain.shared.exceptions import NotFoundError
from app.domain.shared.value_objects import InputData
from app.domain.tool.repository import IToolRepository
from app.domain.agent.repository import IAgentRepository
from app.domain.user.repository import IUserRepository
from app.domain.tool_call.executor import IToolExecutor
from app.domain.tool_call.repository import IToolCallRepository
from app.domain.tool_call.tool_call import ToolCall


@dataclass(frozen=True)
class InvokeToolCommand:
    agent_id: str
    user_id: str
    tool_name: str
    input_data: Dict[str, Any]


class InvokeToolUseCase:
    def __init__(
        self,
        tool_repo: IToolRepository,
        agent_repo: IAgentRepository,
        user_repo: IUserRepository,
        tool_call_repo: IToolCallRepository,
        policy_engine: PolicyEngine,
        executor: IToolExecutor,
    ) -> None:
        self._tool_repo = tool_repo
        self._agent_repo = agent_repo
        self._user_repo = user_repo
        self._tool_call_repo = tool_call_repo
        self._policy_engine = policy_engine
        self._executor = executor

    def execute(self, cmd: InvokeToolCommand) -> ToolCall:
        tool = self._tool_repo.find_by_name(cmd.tool_name)
        if not tool:
            raise NotFoundError(f"Tool not found: {cmd.tool_name}")

        agent = self._agent_repo.find_by_agent_id(cmd.agent_id)
        if not agent:
            raise NotFoundError(f"Agent not registered: {cmd.agent_id}")

        user = self._user_repo.find_by_user_id(cmd.user_id)
        if not user:
            raise NotFoundError(f"User not registered: {cmd.user_id}")

        daily_cost = self._tool_call_repo.get_daily_cost(cmd.tool_name)
        policy_result = self._policy_engine.evaluate(
            PolicyContext(tool=tool, agent=agent, user=user, daily_usage_cost=daily_cost)
        )

        tool_call = ToolCall.create(
            agent_id=cmd.agent_id,
            user_id=cmd.user_id,
            tool_name=cmd.tool_name,
            input_data=InputData(payload=cmd.input_data),
            risk_level=tool.risk_level,
            policy_decision=policy_result.decision,
        )

        if policy_result.decision == PolicyDecision.DENY:
            tool_call.deny(reason=policy_result.reason)
        elif policy_result.decision == PolicyDecision.REQUIRE_APPROVAL:
            tool_call.request_approval()
        else:
            result = self._executor.execute(cmd.tool_name, cmd.input_data)
            tool_call.record_execution(result)

        self._tool_call_repo.save(tool_call)
        return tool_call


class ExecuteApprovedUseCase:
    def __init__(
        self,
        tool_call_repo: IToolCallRepository,
        executor: IToolExecutor,
    ) -> None:
        self._tool_call_repo = tool_call_repo
        self._executor = executor

    def execute(self, request_id: str) -> ToolCall:
        tool_call = self._tool_call_repo.find_by_request_id(request_id)
        if not tool_call:
            raise NotFoundError(f"ToolCall not found: {request_id}")

        result = self._executor.execute(tool_call.tool_name, tool_call.input_data.payload)
        tool_call.record_execution(result)  # raises DomainError if not approved
        self._tool_call_repo.save(tool_call)
        return tool_call
