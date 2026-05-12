import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict

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
