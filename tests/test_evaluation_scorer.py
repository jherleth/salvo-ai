"""Tests for weighted scorer and evaluate_trace orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salvo.evaluation.scorer import compute_score, evaluate_trace, evaluate_trace_async
from salvo.execution.trace import RunTrace, TraceMessage
from salvo.models.result import EvalResult


def _result(
    score: float = 1.0,
    passed: bool = True,
    weight: float = 1.0,
    required: bool = False,
    assertion_type: str = "jmespath",
) -> EvalResult:
    """Create an EvalResult for testing."""
    return EvalResult(
        assertion_type=assertion_type,
        score=score,
        passed=passed,
        weight=weight,
        required=required,
        details="test",
    )


def _make_trace(**overrides) -> RunTrace:
    """Create a minimal RunTrace for testing."""
    defaults = {
        "messages": [
            TraceMessage(role="user", content="Hello"),
            TraceMessage(role="assistant", content="Hi there!"),
        ],
        "tool_calls_made": [],
        "turn_count": 1,
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "latency_seconds": 0.5,
        "final_content": "Hi there!",
        "finish_reason": "stop",
        "model": "gpt-4",
        "provider": "openai",
        "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "scenario_hash": "abc123",
        "cost_usd": 0.01,
    }
    defaults.update(overrides)
    return RunTrace(**defaults)


class TestComputeScore:
    """Test the compute_score function."""

    def test_empty_results_returns_vacuous_pass(self) -> None:
        score, passed, hard_fail = compute_score([], threshold=0.8)
        assert score == 1.0
        assert passed is True
        assert hard_fail is False

    def test_all_passing_equal_weights(self) -> None:
        results = [_result(score=1.0) for _ in range(3)]
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert score == 1.0
        assert passed is True
        assert hard_fail is False

    def test_mixed_pass_fail_equal_weights(self) -> None:
        results = [
            _result(score=1.0, passed=True),
            _result(score=0.0, passed=False),
        ]
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert score == pytest.approx(0.5)
        assert passed is False  # 0.5 < 0.8

    def test_unequal_weights(self) -> None:
        results = [
            _result(score=1.0, passed=True, weight=3.0),
            _result(score=0.0, passed=False, weight=1.0),
        ]
        # Weighted: (1.0*3 + 0.0*1) / (3+1) = 0.75
        score, passed, hard_fail = compute_score(results, threshold=0.7)
        assert score == pytest.approx(0.75)
        assert passed is True  # 0.75 >= 0.7

    def test_threshold_boundary_passes(self) -> None:
        results = [
            _result(score=1.0, passed=True, weight=4.0),
            _result(score=0.0, passed=False, weight=1.0),
        ]
        # Score = 0.8
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert score == pytest.approx(0.8)
        assert passed is True  # score == threshold passes

    def test_threshold_boundary_fails(self) -> None:
        results = [
            _result(score=1.0, passed=True, weight=3.0),
            _result(score=0.0, passed=False, weight=2.0),
        ]
        # Score = 0.6
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert score == pytest.approx(0.6)
        assert passed is False

    def test_required_assertion_failure_causes_hard_fail(self) -> None:
        results = [
            _result(score=1.0, passed=True, weight=9.0),
            _result(score=0.0, passed=False, weight=1.0, required=True),
        ]
        # Score = 0.9 >= 0.8, but required failed
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert score == pytest.approx(0.9)
        assert hard_fail is True
        assert passed is False  # hard_fail overrides

    def test_required_assertion_passing_no_hard_fail(self) -> None:
        results = [
            _result(score=1.0, passed=True, weight=1.0, required=True),
            _result(score=1.0, passed=True, weight=1.0),
        ]
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert hard_fail is False
        assert passed is True

    def test_zero_total_weight(self) -> None:
        results = [
            _result(score=1.0, passed=True, weight=0.0),
        ]
        score, passed, hard_fail = compute_score(results, threshold=0.8)
        assert score == 0.0
        assert passed is False


class TestEvaluateTrace:
    """Test the evaluate_trace orchestration function."""

    def test_end_to_end_jmespath(self) -> None:
        trace = _make_trace(final_content="Hello World")
        assertions = [
            {
                "type": "jmespath",
                "expression": "response.content",
                "operator": "contains",
                "value": "Hello",
                "weight": 1.0,
                "required": False,
            },
        ]
        eval_results, score, passed = evaluate_trace(trace, assertions, threshold=0.8)
        assert len(eval_results) == 1
        assert eval_results[0].passed is True
        assert score == 1.0
        assert passed is True

    def test_end_to_end_mixed_assertions(self) -> None:
        trace = _make_trace(
            final_content="Hello World",
            cost_usd=0.05,
            latency_seconds=1.0,
        )
        assertions = [
            {
                "type": "jmespath",
                "expression": "response.content",
                "operator": "contains",
                "value": "Hello",
                "weight": 1.0,
                "required": False,
            },
            {
                "type": "cost_limit",
                "max_usd": 0.10,
                "weight": 1.0,
                "required": False,
            },
            {
                "type": "latency_limit",
                "max_seconds": 5.0,
                "weight": 1.0,
                "required": False,
            },
        ]
        eval_results, score, passed = evaluate_trace(trace, assertions, threshold=0.8)
        assert len(eval_results) == 3
        assert all(r.passed for r in eval_results)
        assert score == 1.0
        assert passed is True

    def test_end_to_end_failing(self) -> None:
        trace = _make_trace(final_content="Goodbye")
        assertions = [
            {
                "type": "jmespath",
                "expression": "response.content",
                "operator": "eq",
                "value": "Hello",
                "weight": 1.0,
                "required": False,
            },
        ]
        eval_results, score, passed = evaluate_trace(trace, assertions, threshold=0.8)
        assert len(eval_results) == 1
        assert eval_results[0].passed is False
        assert score == 0.0
        assert passed is False

    def test_end_to_end_tool_sequence(self) -> None:
        trace = _make_trace(
            tool_calls_made=[
                {"name": "search", "arguments": {}, "result": "ok"},
                {"name": "answer", "arguments": {}, "result": "ok"},
            ]
        )
        assertions = [
            {
                "type": "tool_sequence",
                "mode": "exact",
                "sequence": ["search", "answer"],
                "weight": 1.0,
                "required": False,
            },
        ]
        eval_results, score, passed = evaluate_trace(trace, assertions, threshold=0.8)
        assert len(eval_results) == 1
        assert eval_results[0].passed is True
        assert passed is True


class TestEvaluateTraceAsync:
    """Test the async evaluate_trace_async orchestration function."""

    @pytest.mark.asyncio
    async def test_evaluate_trace_async_same_as_sync(self) -> None:
        """Verify async produces same results as sync for standard evaluators."""
        trace = _make_trace(final_content="Hello World")
        assertions = [
            {
                "type": "jmespath",
                "expression": "response.content",
                "operator": "contains",
                "value": "Hello",
                "weight": 1.0,
                "required": False,
            },
        ]

        sync_results, sync_score, sync_passed = evaluate_trace(
            trace, assertions, threshold=0.8
        )
        async_results, async_score, async_passed = await evaluate_trace_async(
            trace, assertions, threshold=0.8
        )

        assert len(async_results) == len(sync_results)
        assert async_score == sync_score
        assert async_passed == sync_passed
        assert async_results[0].passed == sync_results[0].passed
        assert async_results[0].score == sync_results[0].score

    @pytest.mark.asyncio
    async def test_evaluate_trace_async_with_mock_judge(self) -> None:
        """Mock a judge evaluator returning known EvalResult, verify included."""
        trace = _make_trace(final_content="Hello World")

        mock_result = EvalResult(
            assertion_type="judge",
            score=0.85,
            passed=True,
            weight=1.0,
            required=False,
            details="mocked judge result",
            metadata={
                "judge_model": "gpt-4o-mini",
                "judge_k": 3,
                "judge_cost_usd": 0.003,
                "per_criterion": [],
            },
        )

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_async = AsyncMock(return_value=mock_result)

        assertions = [
            {
                "type": "judge",
                "criteria": [{"name": "test", "description": "test", "weight": 1.0}],
                "weight": 1.0,
                "required": False,
            },
        ]

        with patch(
            "salvo.evaluation.scorer.get_evaluator",
            return_value=mock_evaluator,
        ):
            results, score, passed = await evaluate_trace_async(
                trace, assertions, threshold=0.8
            )

        assert len(results) == 1
        assert results[0].assertion_type == "judge"
        assert results[0].score == 0.85
        assert results[0].passed is True
        assert results[0].metadata["judge_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_evaluate_trace_async_mixed_standard_and_judge(self) -> None:
        """Mixed standard + mocked judge assertions produce correct weighted score."""
        trace = _make_trace(final_content="Hello World")

        mock_judge_result = EvalResult(
            assertion_type="judge",
            score=0.9,
            passed=True,
            weight=2.0,
            required=False,
            details="mocked judge",
            metadata={"judge_model": "gpt-4o-mini", "judge_k": 3, "judge_cost_usd": 0.003},
        )

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_async = AsyncMock(return_value=mock_judge_result)

        assertions = [
            {
                "type": "jmespath",
                "expression": "response.content",
                "operator": "contains",
                "value": "Hello",
                "weight": 1.0,
                "required": False,
            },
            {
                "type": "judge",
                "criteria": [{"name": "test", "description": "test", "weight": 1.0}],
                "weight": 2.0,
                "required": False,
            },
        ]

        original_get_evaluator = None

        def patched_get_evaluator(assertion_type: str):
            if assertion_type == "judge":
                return mock_evaluator
            from salvo.evaluation.evaluators import get_evaluator as real_get
            return real_get(assertion_type)

        with patch(
            "salvo.evaluation.scorer.get_evaluator",
            side_effect=patched_get_evaluator,
        ):
            results, score, passed = await evaluate_trace_async(
                trace, assertions, threshold=0.8
            )

        assert len(results) == 2
        assert results[0].assertion_type == "jmespath"
        assert results[1].assertion_type == "judge"
        # Weighted: (1.0*1.0 + 0.9*2.0) / (1.0 + 2.0) = 2.8/3.0 ~ 0.933
        assert score == pytest.approx(2.8 / 3.0, rel=1e-3)
        assert passed is True
