"""Tool sequence evaluator -- validates tool call sequences.

Supports three matching modes:
- EXACT: actual == expected (same length, same order)
- IN_ORDER: expected is a subsequence of actual (gaps allowed)
- ANY_ORDER: all expected calls present (bag comparison with counts)
"""

from __future__ import annotations

from collections import Counter

from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


def match_exact(actual: list[str], expected: list[str]) -> tuple[bool, str]:
    """Check that actual == expected exactly.

    On failure, pinpoints the divergence position and shows missing/extra items.
    """
    if len(actual) == 0 and len(expected) > 0:
        return False, f"No tool calls made -- expected {expected}"

    for i, (a, e) in enumerate(zip(actual, expected)):
        if a != e:
            return False, (
                f"Divergence at position {i}: expected {e!r} but got {a!r}. "
                f"Actual: {actual}, Expected: {expected}"
            )

    if len(actual) < len(expected):
        missing = expected[len(actual):]
        return False, (
            f"Too few tool calls: got {len(actual)}, expected {len(expected)}. "
            f"Missing: {missing}"
        )

    if len(actual) > len(expected):
        extra = actual[len(expected):]
        return False, (
            f"Too many tool calls: got {len(actual)}, expected {len(expected)}. "
            f"Extra: {extra}"
        )

    return True, f"Exact match: {actual}"


def match_in_order(actual: list[str], expected: list[str]) -> tuple[bool, str]:
    """Check that expected is a subsequence of actual (gaps allowed).

    Uses a linear scan with an index pointer into expected.
    """
    if len(actual) == 0 and len(expected) > 0:
        return False, f"No tool calls made -- expected {expected}"

    ei = 0  # pointer into expected
    for a in actual:
        if ei < len(expected) and a == expected[ei]:
            ei += 1
    if ei == len(expected):
        return True, f"In-order match: found {expected} within {actual}"

    matched = expected[:ei]
    stalled_at = expected[ei]
    return False, (
        f"In-order match stalled: matched {matched} but could not find "
        f"{stalled_at!r} (expected[{ei}]) in remaining actual calls. "
        f"Actual: {actual}, Expected: {expected}"
    )


def match_any_order(actual: list[str], expected: list[str]) -> tuple[bool, str]:
    """Check that all expected calls are present using count comparison.

    Extra calls in actual are allowed.
    """
    if len(actual) == 0 and len(expected) > 0:
        return False, f"No tool calls made -- expected {expected}"

    actual_counts = Counter(actual)
    expected_counts = Counter(expected)

    missing: list[str] = []
    for call, count in expected_counts.items():
        actual_count = actual_counts.get(call, 0)
        if actual_count < count:
            missing.append(
                f"{call!r} (expected {count}, got {actual_count})"
            )

    if missing:
        return False, f"Missing tool calls: {', '.join(missing)}"

    return True, f"Any-order match: all {expected} found in {actual}"


class ToolSequenceEvaluator(BaseEvaluator):
    """Evaluates tool call sequence assertions."""

    def evaluate(self, trace: RunTrace, assertion: dict) -> EvalResult:
        """Validate tool call sequence against the expected pattern."""
        mode = assertion["mode"].lower()
        expected = assertion["sequence"]
        weight = assertion.get("weight", 1.0)
        required = assertion.get("required", False)

        actual = [tc["name"] for tc in trace.tool_calls_made]

        dispatch = {
            "exact": match_exact,
            "in_order": match_in_order,
            "any_order": match_any_order,
        }

        match_fn = dispatch.get(mode)
        if match_fn is None:
            return EvalResult(
                assertion_type="tool_sequence",
                score=0.0,
                passed=False,
                weight=weight,
                required=required,
                details=f"Unknown mode {mode!r}. Available: {sorted(dispatch.keys())}",
            )

        passed, details = match_fn(actual, expected)

        return EvalResult(
            assertion_type="tool_sequence",
            score=1.0 if passed else 0.0,
            passed=passed,
            weight=weight,
            required=required,
            details=details,
        )
