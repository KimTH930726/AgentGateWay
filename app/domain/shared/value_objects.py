import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.domain.enums import ExecutionStatus


@dataclass(frozen=True)
class InputData:
    """Immutable value object wrapping a tool's input payload."""

    payload: Dict[str, Any]

    @property
    def hash(self) -> str:
        try:
            serialised = json.dumps(self.payload, sort_keys=True, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"InputData payload is not JSON-serialisable: {exc}") from exc
        return hashlib.sha256(serialised.encode()).hexdigest()[:16]

    def __hash__(self) -> int:
        return hash(self.hash)

    def __eq__(self, other: object) -> bool:
        # Compare by actual payload, not hash, to avoid false equality on hash collision.
        return isinstance(other, InputData) and self.payload == other.payload


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable value object returned by the tool executor."""

    status: ExecutionStatus
    output: Dict[str, Any]
    cost: float
    duration_ms: int = 0
    tokens_used: int = 0


@dataclass(frozen=True)
class CandidateTool:
    """One of multiple tools the agent considered before selecting this one.

    `reason_not_selected` lets the agent record why an alternative lost out,
    which is critical for governance review when behaviour later goes wrong.
    """

    tool_name: str
    reason_not_selected: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"tool_name": self.tool_name, "reason_not_selected": self.reason_not_selected}


@dataclass(frozen=True)
class ToolSelection:
    """Agent's reasoning about why it picked the tool it eventually invoked."""

    selected_reason: str = ""
    candidates: List[CandidateTool] = field(default_factory=list)

    def candidates_as_dicts(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.candidates]

    @classmethod
    def from_storage(
        cls,
        selected_reason: Optional[str],
        candidates: Optional[List[Dict[str, Any]]],
    ) -> "ToolSelection":
        return cls(
            selected_reason=selected_reason or "",
            candidates=[
                CandidateTool(
                    tool_name=c.get("tool_name", ""),
                    reason_not_selected=c.get("reason_not_selected", ""),
                )
                for c in (candidates or [])
            ],
        )
