from typing import Optional, Sequence

from app.domain.enums import PolicyDecision
from app.domain.policy.context import PolicyContext, PolicyResult
from app.domain.policy.rules import DEFAULT_RULES, PolicyRule


class PolicyEngine:
    """
    Domain service — stateless, pure policy evaluation.
    Iterates an ordered rule chain; first non-None result wins.
    Inject a custom rule list to override defaults (useful in tests).
    """

    def __init__(self, rules: Optional[Sequence[PolicyRule]] = None) -> None:
        self._rules: Sequence[PolicyRule] = rules if rules is not None else DEFAULT_RULES

    def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        for rule in self._rules:
            result = rule.evaluate(ctx)
            if result is not None:
                return result
        return PolicyResult(PolicyDecision.ALLOW, "All policy checks passed")
