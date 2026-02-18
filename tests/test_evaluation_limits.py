"""Tests for cost limit and latency limit evaluators."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from salvo.evaluation.evaluators.cost_limit import CostLimitEvaluator
from salvo.evaluation.evaluators.latency_limit import LatencyLimitEvaluator
from salvo.execution.trace import RunTrace, TraceMessage


def _make_trace(
    cost_usd: float | None = 0.05,
    latency_seconds: float = 1.0,
) -> RunTrace:
    """Create a RunTrace for testing limits."""
    return RunTrace(
        messages=[
            TraceMessage(role="user", content="Hello"),
            TraceMessage(role="assistant", content="Done"),
        ],
        tool_calls_made=[],
        turn_count=1,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        latency_seconds=latency_seconds,
        final_content="Done",
        finish_reason="stop",
        model="gpt-4",
        provider="openai",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scenario_hash="abc123",
        cost_usd=cost_usd,
    )


class TestCostLimitEvaluator:
    """Test cost limit evaluator."""

    def test_passes_when_cost_under_limit(self) -> None:
        trace = _make_trace(cost_usd=0.05)
        evaluator = CostLimitEvaluator()
        assertion = {
            "type": "cost_limit",
            "max_usd": 0.10,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True
        assert result.score == 1.0
        assert result.assertion_type == "cost_limit"

    def test_passes_when_cost_equals_limit(self) -> None:
        trace = _make_trace(cost_usd=0.10)
        evaluator = CostLimitEvaluator()
        assertion = {
            "type": "cost_limit",
            "max_usd": 0.10,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True

    def test_fails_when_cost_exceeds_limit(self) -> None:
        trace = _make_trace(cost_usd=0.20)
        evaluator = CostLimitEvaluator()
        assertion = {
            "type": "cost_limit",
            "max_usd": 0.10,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0

    def test_fails_when_cost_is_none(self) -> None:
        trace = _make_trace(cost_usd=None)
        evaluator = CostLimitEvaluator()
        assertion = {
            "type": "cost_limit",
            "max_usd": 0.10,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0
        assert "unknown" in result.details.lower()

    def test_weight_and_required_carry_over(self) -> None:
        trace = _make_trace(cost_usd=0.05)
        evaluator = CostLimitEvaluator()
        assertion = {
            "type": "cost_limit",
            "max_usd": 0.10,
            "weight": 3.0,
            "required": True,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.weight == 3.0
        assert result.required is True


class TestLatencyLimitEvaluator:
    """Test latency limit evaluator."""

    def test_passes_when_latency_under_limit(self) -> None:
        trace = _make_trace(latency_seconds=1.0)
        evaluator = LatencyLimitEvaluator()
        assertion = {
            "type": "latency_limit",
            "max_seconds": 5.0,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True
        assert result.score == 1.0
        assert result.assertion_type == "latency_limit"

    def test_passes_when_latency_equals_limit(self) -> None:
        trace = _make_trace(latency_seconds=5.0)
        evaluator = LatencyLimitEvaluator()
        assertion = {
            "type": "latency_limit",
            "max_seconds": 5.0,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True

    def test_fails_when_latency_exceeds_limit(self) -> None:
        trace = _make_trace(latency_seconds=10.0)
        evaluator = LatencyLimitEvaluator()
        assertion = {
            "type": "latency_limit",
            "max_seconds": 5.0,
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0

    def test_weight_and_required_carry_over(self) -> None:
        trace = _make_trace(latency_seconds=1.0)
        evaluator = LatencyLimitEvaluator()
        assertion = {
            "type": "latency_limit",
            "max_seconds": 5.0,
            "weight": 2.5,
            "required": True,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.weight == 2.5
        assert result.required is True
