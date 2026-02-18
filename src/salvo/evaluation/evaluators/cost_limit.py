"""Cost limit evaluator -- passes when cost <= max_usd."""

from __future__ import annotations

from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


class CostLimitEvaluator(BaseEvaluator):
    """Evaluates whether run cost is within the specified limit."""

    def evaluate(self, trace: RunTrace, assertion: dict) -> EvalResult:
        """Check trace.cost_usd against max_usd threshold."""
        max_usd = assertion["max_usd"]
        weight = assertion.get("weight", 1.0)
        required = assertion.get("required", False)

        if trace.cost_usd is None:
            return EvalResult(
                assertion_type="cost_limit",
                score=0.0,
                passed=False,
                weight=weight,
                required=required,
                details=f"Cost unknown (None) -- cannot verify limit of ${max_usd:.4f}",
            )

        passed = trace.cost_usd <= max_usd
        details = f"Cost ${trace.cost_usd:.4f} vs limit ${max_usd:.4f}"

        return EvalResult(
            assertion_type="cost_limit",
            score=1.0 if passed else 0.0,
            passed=passed,
            weight=weight,
            required=required,
            details=details,
        )
