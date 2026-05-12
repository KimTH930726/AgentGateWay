from abc import ABC, abstractmethod
from typing import Any, Dict

from app.domain.shared.value_objects import ExecutionResult


class IToolExecutor(ABC):
    """Port — the real or mock executor must implement this."""

    @abstractmethod
    def execute(self, tool_name: str, input_data: Dict[str, Any]) -> ExecutionResult: ...
