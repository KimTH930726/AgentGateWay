from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.agent.agent import Agent


class IAgentRepository(ABC):

    @abstractmethod
    def find_by_agent_id(self, agent_id: str) -> Optional[Agent]: ...

    @abstractmethod
    def find_all(self) -> List[Agent]: ...

    @abstractmethod
    def save(self, agent: Agent) -> Agent: ...

    @abstractmethod
    def update(self, agent_id: str, updates: dict) -> Optional[Agent]: ...
