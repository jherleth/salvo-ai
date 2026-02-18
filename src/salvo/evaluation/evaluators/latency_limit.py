"""Latency limit evaluator -- passes when latency <= max_seconds."""

from __future__ import annotations

from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


class LatencyLimitEvaluator(BaseEvaluator):
    """Evaluates whether run latency is within the specified limit."""

    def evaluate(self, trace: RunTrace, assertion: dict) -> EvalResult:
        """Check trace.latency_seconds against max_seconds threshold."""
        max_seconds = assertion["max_seconds"]
        weight = assertion.get("weight", 1.0)
        required = assertion.get("required", False)

        passed = trace.latency_seconds <= max_seconds
        details = f"Latency {trace.latency_seconds:.3f}s vs limit {max_seconds:.3f}s"

        return EvalResult(
            assertion_type="latency_limit",
            score=1.0 if passed else 0.0,
            passed=passed,
            weight=weight,
            required=required,
            details=details,
        )
