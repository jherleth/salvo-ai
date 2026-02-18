"""Tests for tool sequence evaluator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from salvo.evaluation.evaluators.tool_sequence import (
    ToolSequenceEvaluator,
    match_any_order,
    match_exact,
    match_in_order,
)
from salvo.execution.trace import RunTrace, TraceMessage


def _make_trace(tool_names: list[str] | None = None) -> RunTrace:
    """Create a RunTrace with specified tool call names."""
    tool_calls = [{"name": n, "arguments": {}, "result": "ok"} for n in (tool_names or [])]
    return RunTrace(
        messages=[
            TraceMessage(role="user", content="Hello"),
            TraceMessage(role="assistant", content="Done"),
        ],
        tool_calls_made=tool_calls,
        turn_count=1,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        latency_seconds=0.5,
        final_content="Done",
        finish_reason="stop",
        model="gpt-4",
        provider="openai",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scenario_hash="abc123",
    )


class TestMatchExact:
    """Test exact sequence matching."""

    def test_exact_match_success(self) -> None:
        passed, msg = match_exact(["search", "answer"], ["search", "answer"])
        assert passed is True

    def test_exact_match_failure_different_item(self) -> None:
        passed, msg = match_exact(["search", "answer"], ["search", "summarize"])
        assert passed is False
        assert "position" in msg.lower() or "1" in msg

    def test_exact_match_failure_too_few(self) -> None:
        passed, msg = match_exact(["search"], ["search", "answer"])
        assert passed is False
        assert "missing" in msg.lower() or "fewer" in msg.lower() or "expected" in msg.lower()

    def test_exact_match_failure_too_many(self) -> None:
        passed, msg = match_exact(["search", "answer", "extra"], ["search", "answer"])
        assert passed is False
        assert "extra" in msg.lower()


class TestMatchInOrder:
    """Test in-order subsequence matching."""

    def test_in_order_success_with_gaps(self) -> None:
        passed, msg = match_in_order(["a", "b", "c", "d"], ["a", "c"])
        assert passed is True

    def test_in_order_success_exact(self) -> None:
        passed, msg = match_in_order(["a", "b"], ["a", "b"])
        assert passed is True

    def test_in_order_failure_wrong_order(self) -> None:
        passed, msg = match_in_order(["b", "a"], ["a", "b"])
        assert passed is False

    def test_in_order_failure_stalled(self) -> None:
        passed, msg = match_in_order(["a", "c"], ["a", "b", "c"])
        assert passed is False
        assert "b" in msg  # Should mention what stalled


class TestMatchAnyOrder:
    """Test any-order (bag) matching."""

    def test_any_order_success(self) -> None:
        passed, msg = match_any_order(["b", "a", "c"], ["a", "b", "c"])
        assert passed is True

    def test_any_order_success_extra_calls(self) -> None:
        passed, msg = match_any_order(["a", "b", "c", "d"], ["a", "c"])
        assert passed is True

    def test_any_order_failure_missing(self) -> None:
        passed, msg = match_any_order(["a", "b"], ["a", "b", "c"])
        assert passed is False
        assert "c" in msg  # Should mention the missing call

    def test_any_order_failure_insufficient_count(self) -> None:
        passed, msg = match_any_order(["a"], ["a", "a"])
        assert passed is False


class TestZeroToolCalls:
    """Test zero tool calls edge case."""

    def test_zero_calls_with_expected(self) -> None:
        passed, msg = match_exact([], ["search"])
        assert passed is False
        assert "no tool calls" in msg.lower()

    def test_zero_calls_in_order(self) -> None:
        passed, msg = match_in_order([], ["search"])
        assert passed is False
        assert "no tool calls" in msg.lower()

    def test_zero_calls_any_order(self) -> None:
        passed, msg = match_any_order([], ["search"])
        assert passed is False
        assert "no tool calls" in msg.lower()


class TestToolSequenceEvaluator:
    """Test the evaluator dispatches correctly."""

    def test_evaluate_exact_pass(self) -> None:
        trace = _make_trace(["search", "answer"])
        evaluator = ToolSequenceEvaluator()
        assertion = {
            "type": "tool_sequence",
            "mode": "exact",
            "sequence": ["search", "answer"],
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True
        assert result.score == 1.0
        assert result.assertion_type == "tool_sequence"

    def test_evaluate_in_order_pass(self) -> None:
        trace = _make_trace(["a", "b", "c"])
        evaluator = ToolSequenceEvaluator()
        assertion = {
            "type": "tool_sequence",
            "mode": "in_order",
            "sequence": ["a", "c"],
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True

    def test_evaluate_any_order_pass(self) -> None:
        trace = _make_trace(["c", "b", "a"])
        evaluator = ToolSequenceEvaluator()
        assertion = {
            "type": "tool_sequence",
            "mode": "any_order",
            "sequence": ["a", "b", "c"],
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True

    def test_evaluate_exact_fail(self) -> None:
        trace = _make_trace(["search"])
        evaluator = ToolSequenceEvaluator()
        assertion = {
            "type": "tool_sequence",
            "mode": "exact",
            "sequence": ["search", "answer"],
            "weight": 2.0,
            "required": True,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0
        assert result.weight == 2.0
        assert result.required is True

    def test_evaluate_mode_case_insensitive(self) -> None:
        trace = _make_trace(["a", "b"])
        evaluator = ToolSequenceEvaluator()
        assertion = {
            "type": "tool_sequence",
            "mode": "EXACT",
            "sequence": ["a", "b"],
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True
