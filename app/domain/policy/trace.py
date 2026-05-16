"""Per-rule evaluation record — populated by PolicyEngine as it walks the chain."""
from dataclasses import dataclass
from typing import Any, Dict, List

from app.domain.enums import RuleOutcome


@dataclass(frozen=True)
class RuleEvaluation:
    rule_name: str
    outcome: RuleOutcome
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule_name,
            "outcome": self.outcome.value,
            "reason": self.reason,
        }


def trace_to_dicts(trace: List["RuleEvaluation"]) -> List[Dict[str, Any]]:
    return [e.to_dict() for e in trace]


def trace_from_dicts(rows: List[Dict[str, Any]]) -> List["RuleEvaluation"]:
    return [
        RuleEvaluation(
            rule_name=row.get("rule", ""),
            outcome=RuleOutcome(row["outcome"]),
            reason=row.get("reason", ""),
        )
        for row in rows or []
    ]
