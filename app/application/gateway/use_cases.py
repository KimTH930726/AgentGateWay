from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.domain.agent_tool_policy.repository import IAgentToolPolicyRepository
from app.domain.enums import PolicyDecision
from app.domain.policy.context import PolicyContext
from app.domain.policy.policy_engine import PolicyEngine
from app.domain.shared.exceptions import NotFoundError
from app.domain.shared.value_objects import CandidateTool, InputData, ToolSelection
from app.domain.tool.repository import IToolRepository
from app.domain.agent.repository import IAgentRepository
from app.domain.user.repository import IUserRepository
from app.domain.tool_call.executor import IToolExecutor
from app.domain.tool_call.repository import IToolCallRepository
from app.domain.tool_call.tool_call import ToolCall
import uuid


@dataclass(frozen=True)
class CandidateToolDTO:
    tool_name: str
    reason_not_selected: str = ""


@dataclass(frozen=True)
class InvokeToolCommand:
    agent_id: str
    user_id: str
    tool_name: str
    input_data: Dict[str, Any]
    trace_id: str = field(default="")
    selected_reason: str = field(default="")
    candidates: List[CandidateToolDTO] = field(default_factory=list)


class InvokeToolUseCase:
    def __init__(
        self,
        tool_repo: IToolRepository,
        agent_repo: IAgentRepository,
        user_repo: IUserRepository,
        tool_call_repo: IToolCallRepository,
        policy_engine: PolicyEngine,
        executor: IToolExecutor,
        agent_tool_policy_repo: Optional[IAgentToolPolicyRepository] = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._agent_repo = agent_repo
        self._user_repo = user_repo
        self._tool_call_repo = tool_call_repo
        self._policy_engine = policy_engine
        self._executor = executor
        self._agent_tool_policy_repo = agent_tool_policy_repo

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

        # --- governance context ------------------------------------------
        daily_cost = self._tool_call_repo.get_daily_cost(cmd.tool_name)
        agent_daily_cost = self._tool_call_repo.get_agent_daily_cost(cmd.agent_id)
        agent_daily_tokens = self._tool_call_repo.get_agent_daily_tokens(cmd.agent_id)
        agent_monthly_cost = self._tool_call_repo.get_agent_monthly_cost(cmd.agent_id)
        policies = (
            self._agent_tool_policy_repo.find_by_agent(cmd.agent_id)
            if self._agent_tool_policy_repo is not None
            else []
        )

        policy_result = self._policy_engine.evaluate(
            PolicyContext(
                tool=tool,
                agent=agent,
                user=user,
                daily_usage_cost=daily_cost,
                agent_daily_cost=agent_daily_cost,
                agent_monthly_cost=agent_monthly_cost,
                agent_daily_tokens=agent_daily_tokens,
                agent_tool_policies=policies,
            )
        )

        trace_id = cmd.trace_id or str(uuid.uuid4())

        selection = ToolSelection(
            selected_reason=cmd.selected_reason,
            candidates=[
                CandidateTool(tool_name=c.tool_name, reason_not_selected=c.reason_not_selected)
                for c in cmd.candidates
            ],
        )

        tool_call = ToolCall.create(
            agent_id=cmd.agent_id,
            user_id=cmd.user_id,
            tool_name=cmd.tool_name,
            input_data=InputData(payload=cmd.input_data),
            risk_level=tool.risk_level,
            policy_decision=policy_result.decision,
            trace_id=trace_id,
            policy_reason=policy_result.reason,
            tool_selection=selection,
            rule_trace=policy_result.trace,
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
