from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.agent_tool_policy.agent_tool_policy import AgentToolPolicy


class IAgentToolPolicyRepository(ABC):
    """Port — manages per-agent allowlist/denylist entries."""

    @abstractmethod
    def save(self, policy: AgentToolPolicy) -> AgentToolPolicy: ...

    @abstractmethod
    def find_by_id(self, policy_id: str) -> Optional[AgentToolPolicy]: ...

    @abstractmethod
    def find_by_agent(self, agent_id: str) -> List[AgentToolPolicy]: ...

    @abstractmethod
    def find_all(self) -> List[AgentToolPolicy]: ...

    @abstractmethod
    def update(self, policy_id: str, updates: dict) -> Optional[AgentToolPolicy]: ...

    @abstractmethod
    def delete(self, policy_id: str) -> bool: ...
