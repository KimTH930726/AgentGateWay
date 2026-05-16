from typing import List, Optional, Sequence

from app.domain.enums import PolicyDecision, RuleOutcome
from app.domain.policy.context import PolicyContext, PolicyResult
from app.domain.policy.rules import DEFAULT_RULES, PolicyRule
from app.domain.policy.trace import RuleEvaluation


class PolicyEngine:
    """
    Domain service — stateless, pure policy evaluation.
    Iterates an ordered rule chain; first non-None result wins.
    Inject a custom rule list to override defaults (useful in tests).

    The returned PolicyResult now also carries a per-rule `trace` listing every
    rule that was consulted, in order, with its outcome. Rules that fired with
    DENY/REQUIRE_APPROVAL short-circuit the chain, so trailing rules are not
    represented — that matches the actual evaluation history.
    """

    def __init__(self, rules: Optional[Sequence[PolicyRule]] = None) -> None:
        self._rules: Sequence[PolicyRule] = rules if rules is not None else DEFAULT_RULES

    def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        trace: List[RuleEvaluation] = []
        for rule in self._rules:
            result = rule.evaluate(ctx)
            rule_name = type(rule).__name__
            if result is None:
                trace.append(RuleEvaluation(rule_name=rule_name, outcome=RuleOutcome.PASS))
                continue
            outcome = (
                RuleOutcome.DENY
                if result.decision == PolicyDecision.DENY
                else RuleOutcome.REQUIRE_APPROVAL
            )
            trace.append(
                RuleEvaluation(rule_name=rule_name, outcome=outcome, reason=result.reason)
            )
            return PolicyResult(decision=result.decision, reason=result.reason, trace=trace)
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="All policy checks passed",
            trace=trace,
        )
