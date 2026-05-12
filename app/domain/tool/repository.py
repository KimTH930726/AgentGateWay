from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.tool.tool import Tool


class IToolRepository(ABC):

    @abstractmethod
    def find_by_tool_id(self, tool_id: str) -> Optional[Tool]: ...

    @abstractmethod
    def find_by_name(self, name: str) -> Optional[Tool]: ...

    @abstractmethod
    def find_all(self) -> List[Tool]: ...

    @abstractmethod
    def save(self, tool: Tool) -> Tool: ...

    @abstractmethod
    def update(self, tool_id: str, updates: dict) -> Optional[Tool]: ...

    @abstractmethod
    def delete(self, tool_id: str) -> bool: ...
