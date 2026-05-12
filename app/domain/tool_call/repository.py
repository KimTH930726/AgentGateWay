from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.tool_call.tool_call import ToolCall


class IToolCallRepository(ABC):
    """Port — infrastructure must implement this interface."""

    @abstractmethod
    def save(self, tool_call: ToolCall) -> None:
        """Upsert the aggregate (tool_calls + approvals rows)."""

    @abstractmethod
    def find_by_request_id(self, request_id: str) -> Optional[ToolCall]: ...

    @abstractmethod
    def find_by_approval_id(self, approval_id: str) -> Optional[ToolCall]:
        """Find the ToolCall that owns this approval UUID."""

    @abstractmethod
    def find_all(self, limit: int = 50, offset: int = 0) -> List[ToolCall]: ...

    @abstractmethod
    def find_with_approvals(self, pending_only: bool = False) -> List[ToolCall]:
        """Return tool calls that have an approval record."""

    @abstractmethod
    def get_daily_cost(self, tool_name: str) -> float: ...
