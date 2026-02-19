"""Tests for JudgeEvaluator and resolve_judge_config."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salvo.adapters.base import AdapterTurnResult, TokenUsage, ToolCallResult
from salvo.evaluation.evaluators import get_evaluator
from salvo.evaluation.evaluators.judge import JudgeEvaluator, resolve_judge_config
from salvo.execution.trace import RunTrace


def _make_trace(final_content: str = "Agent response") -> RunTrace:
    return RunTrace(
        messages=[],
        tool_calls_made=[],
        turn_count=1,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_seconds=1.0,
        final_content=final_content,
        finish_reason="stop",
        model="gpt-4o",
        provider="openai",
        timestamp=datetime.now(),
        scenario_hash="abc123",
    )


def _make_adapter_result(scores: dict, tool_name: str = "score_criteria") -> AdapterTurnResult:
    """Create an AdapterTurnResult with tool call containing scores."""
    return AdapterTurnResult(
        content=None,
        tool_calls=[
            ToolCallResult(
                id="call_test",
                name=tool_name,
                arguments=scores,
            )
        ],
        usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
        raw_response={},
        finish_reason="stop",
    )


SAMPLE_ASSERTION = {
    "type": "judge",
    "criteria": [
        {"name": "accuracy", "description": "Factually correct", "weight": 1.0},
        {"name": "clarity", "description": "Easy to understand", "weight": 0.5},
    ],
    "weight": 1.0,
    "required": False,
}


class TestJudgeEvaluatorRegistered:
    def test_judge_evaluator_registered(self):
        evaluator = get_evaluator("judge")
        assert isinstance(evaluator, JudgeEvaluator)


class TestEvaluateAsync:
    @pytest.mark.asyncio
    async def test_evaluate_async_pass(self):
        """Mock adapter returns valid scores above threshold for 3 calls."""
        mock_adapter = MagicMock()
        mock_adapter.provider_name.return_value = "openai"
        mock_adapter.send_turn = AsyncMock(
            return_value=_make_adapter_result(
                {
                    "accuracy": {"score": 0.9, "reasoning": "Good"},
                    "clarity": {"score": 0.85, "reasoning": "Clear"},
                }
            )
        )

        evaluator = JudgeEvaluator()
        with patch(
            "salvo.evaluation.evaluators.judge.get_adapter", return_value=mock_adapter
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost", return_value=0.001
        ):
            result = await evaluator.evaluate_async(_make_trace(), SAMPLE_ASSERTION)

        assert result.passed is True
        assert result.score > 0.8
        assert result.assertion_type == "judge"
        assert "judge=" in result.details

    @pytest.mark.asyncio
    async def test_evaluate_async_fail(self):
        """Mock adapter returns scores below threshold."""
        mock_adapter = MagicMock()
        mock_adapter.provider_name.return_value = "openai"
        mock_adapter.send_turn = AsyncMock(
            return_value=_make_adapter_result(
                {
                    "accuracy": {"score": 0.3, "reasoning": "Bad"},
                    "clarity": {"score": 0.2, "reasoning": "Unclear"},
                }
            )
        )

        evaluator = JudgeEvaluator()
        with patch(
            "salvo.evaluation.evaluators.judge.get_adapter", return_value=mock_adapter
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost", return_value=0.001
        ):
            result = await evaluator.evaluate_async(_make_trace(), SAMPLE_ASSERTION)

        assert result.passed is False
        assert result.score < 0.8

    @pytest.mark.asyncio
    async def test_evaluate_async_parse_failure_fallback(self):
        """First call returns no tool calls but text JSON -- text fallback works."""
        import json

        text_scores = json.dumps({
            "accuracy": {"score": 0.9, "reasoning": "Good"},
            "clarity": {"score": 0.8, "reasoning": "Clear"},
        })

        text_result = AdapterTurnResult(
            content=text_scores,
            tool_calls=[],
            usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
            raw_response={},
            finish_reason="stop",
        )

        mock_adapter = MagicMock()
        mock_adapter.provider_name.return_value = "openai"
        mock_adapter.send_turn = AsyncMock(return_value=text_result)

        evaluator = JudgeEvaluator()
        with patch(
            "salvo.evaluation.evaluators.judge.get_adapter", return_value=mock_adapter
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost", return_value=0.001
        ):
            result = await evaluator.evaluate_async(_make_trace(), SAMPLE_ASSERTION)

        assert result.passed is True
        assert result.score > 0.0

    @pytest.mark.asyncio
    async def test_evaluate_async_all_parse_failures(self):
        """All k calls return garbage -- verify judge_parse_failed in details."""
        garbage_result = AdapterTurnResult(
            content="I can't evaluate this",
            tool_calls=[],
            usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
            raw_response={},
            finish_reason="stop",
        )

        mock_adapter = MagicMock()
        mock_adapter.provider_name.return_value = "openai"
        mock_adapter.send_turn = AsyncMock(return_value=garbage_result)

        evaluator = JudgeEvaluator()
        with patch(
            "salvo.evaluation.evaluators.judge.get_adapter", return_value=mock_adapter
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost", return_value=0.001
        ):
            result = await evaluator.evaluate_async(_make_trace(), SAMPLE_ASSERTION)

        assert result.passed is False
        assert result.score == 0.0
        assert "judge_parse_failed" in result.details

    @pytest.mark.asyncio
    async def test_evaluate_async_cost_tracked(self):
        """Verify judge cost accumulated in details string."""
        mock_adapter = MagicMock()
        mock_adapter.provider_name.return_value = "openai"
        mock_adapter.send_turn = AsyncMock(
            return_value=_make_adapter_result(
                {
                    "accuracy": {"score": 0.9, "reasoning": "Good"},
                    "clarity": {"score": 0.8, "reasoning": "Clear"},
                }
            )
        )

        evaluator = JudgeEvaluator()
        with patch(
            "salvo.evaluation.evaluators.judge.get_adapter", return_value=mock_adapter
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost", return_value=0.001
        ):
            result = await evaluator.evaluate_async(_make_trace(), SAMPLE_ASSERTION)

        # 3 calls * 0.001 = 0.003
        assert "judge_cost=$0.003000" in result.details


class TestResolveJudgeConfig:
    def test_resolve_judge_config_defaults(self):
        result = resolve_judge_config({})
        assert result["judge_adapter"] == "openai"
        assert result["judge_model"] == "gpt-4o-mini"
        assert result["k"] == 3
        assert result["temperature"] == 0.0
        assert result["max_tokens"] == 1024

    def test_resolve_judge_config_assertion_override(self):
        assertion = {"judge_model": "gpt-4o", "k": 5}
        result = resolve_judge_config(assertion)
        assert result["judge_model"] == "gpt-4o"
        assert result["k"] == 5
        # Defaults for unspecified
        assert result["judge_adapter"] == "openai"

    def test_resolve_judge_config_project_override(self):
        project_config = {
            "adapter": "anthropic",
            "model": "claude-haiku-4-5",
            "k": 7,
            "temperature": 0.5,
            "max_tokens": 2048,
        }
        result = resolve_judge_config({}, project_config=project_config)
        assert result["judge_adapter"] == "anthropic"
        assert result["judge_model"] == "claude-haiku-4-5"
        assert result["k"] == 7
        assert result["temperature"] == 0.5
        assert result["max_tokens"] == 2048
