"""JMESPath evaluator -- queries trace data with JMESPath expressions.

Supports 8 comparison operators: eq, ne, gt, gte, lt, lte, contains, regex.
"""

from __future__ import annotations

import re
from typing import Any

import jmespath
import jmespath.exceptions

from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


def build_trace_data(trace: RunTrace) -> dict:
    """Convert a RunTrace into a queryable dict for JMESPath.

    Structure::

        {
            "response": {"content": ..., "finish_reason": ...},
            "turns": [{"role": ..., "content": ..., ...}, ...],
            "tool_calls": [{"name": ..., "arguments": ..., ...}, ...],
            "metadata": {
                "model": ..., "provider": ..., "cost_usd": ...,
                "latency_seconds": ..., "input_tokens": ...,
                "output_tokens": ..., "total_tokens": ...,
                "turn_count": ..., "finish_reason": ...
            }
        }
    """
    # Build turns from messages
    turns = []
    for msg in trace.messages:
        turn: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.tool_calls is not None:
            turn["tool_calls"] = msg.tool_calls
        if msg.tool_call_id is not None:
            turn["tool_call_id"] = msg.tool_call_id
        if msg.tool_name is not None:
            turn["tool_name"] = msg.tool_name
        turns.append(turn)

    return {
        "response": {
            "content": trace.final_content,
            "finish_reason": trace.finish_reason,
        },
        "turns": turns,
        "tool_calls": list(trace.tool_calls_made),
        "metadata": {
            "model": trace.model,
            "provider": trace.provider,
            "cost_usd": trace.cost_usd,
            "latency_seconds": trace.latency_seconds,
            "input_tokens": trace.input_tokens,
            "output_tokens": trace.output_tokens,
            "total_tokens": trace.total_tokens,
            "turn_count": trace.turn_count,
            "finish_reason": trace.finish_reason,
        },
    }


def compare(actual: Any, operator: str, expected: Any) -> bool:
    """Apply a comparison operator between actual and expected values.

    Returns False if actual is None (path not found).
    """
    if actual is None:
        return False

    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected

    # Numeric comparisons with coercion
    if operator in ("gt", "gte", "lt", "lte"):
        try:
            a = float(actual)
            e = float(expected)
        except (ValueError, TypeError):
            return False
        if operator == "gt":
            return a > e
        if operator == "gte":
            return a >= e
        if operator == "lt":
            return a < e
        # lte
        return a <= e

    if operator == "exists":
        return True  # actual is not None (already checked above)

    if operator == "contains":
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, list):
            return expected in actual
        return False

    if operator == "regex":
        try:
            return re.search(str(expected), str(actual)) is not None
        except re.error:
            return False

    return False


class JMESPathEvaluator(BaseEvaluator):
    """Evaluates JMESPath assertions against run traces."""

    def evaluate(self, trace: RunTrace, assertion: dict) -> EvalResult:
        """Query trace data with JMESPath and compare result."""
        expression = assertion["expression"]
        operator = assertion["operator"]
        expected = assertion.get("value")
        weight = assertion.get("weight", 1.0)
        required = assertion.get("required", False)

        data = build_trace_data(trace)

        try:
            actual = jmespath.search(expression, data)
        except jmespath.exceptions.ParseError as exc:
            return EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=weight,
                required=required,
                details=f"JMESPath parse error: {exc}",
            )

        passed = compare(actual, operator, expected)

        details = (
            f"path={expression!r} operator={operator} "
            f"expected={expected!r} actual={actual!r}"
        )

        return EvalResult(
            assertion_type="jmespath",
            score=1.0 if passed else 0.0,
            passed=passed,
            weight=weight,
            required=required,
            details=details,
        )
