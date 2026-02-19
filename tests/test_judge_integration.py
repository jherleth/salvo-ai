"""End-to-end integration tests for judge assertions in the trial runner pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)
from salvo.execution.trace import RunTrace, TraceMessage
from salvo.execution.trial_runner import TrialRunner
from salvo.models.result import EvalResult
from salvo.models.scenario import Assertion, Scenario, ToolDef
from salvo.models.trial import TrialStatus


def _make_scenario(
    *,
    assertions: list[dict] | None = None,
    system_prompt: str = "You are a helpful assistant.",
    prompt: str = "Say hello",
) -> Scenario:
    """Build a minimal Scenario for testing."""
    assertion_objs = []
    for a in (assertions or []):
        assertion_objs.append(Assertion(**a))

    return Scenario(
        description="Test scenario",
        adapter="openai",
        model="gpt-4o-mini",
        system_prompt=system_prompt,
        prompt=prompt,
        assertions=assertion_objs,
        threshold=0.8,
    )


def _make_agent_trace() -> RunTrace:
    """Create a realistic agent trace for integration tests."""
    return RunTrace(
        messages=[
            TraceMessage(role="user", content="Say hello"),
            TraceMessage(role="assistant", content="Hello! How can I help you?"),
        ],
        tool_calls_made=[],
        turn_count=1,
        input_tokens=50,
        output_tokens=30,
        total_tokens=80,
        latency_seconds=0.8,
        final_content="Hello! How can I help you?",
        finish_reason="stop",
        model="gpt-4o-mini",
        provider="openai",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scenario_hash="abc123",
        cost_usd=0.001,
    )


def _make_judge_adapter_result(scores: dict) -> AdapterTurnResult:
    """Create a judge adapter result with tool call containing criterion scores."""
    return AdapterTurnResult(
        content=None,
        tool_calls=[
            ToolCallResult(
                id="call_judge",
                name="score_criteria",
                arguments=scores,
            )
        ],
        usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
        raw_response={},
        finish_reason="stop",
    )


class TestE2EJudgeAssertionInTrial:
    """Test that a judge assertion flows through the full TrialRunner pipeline."""

    @pytest.mark.asyncio
    async def test_e2e_judge_assertion_in_trial(self) -> None:
        """Create a Scenario with a judge assertion, mock both agent and judge,
        run through TrialRunner, verify judge assertion appears in eval_results."""
        scenario = _make_scenario(
            assertions=[
                {
                    "type": "judge",
                    "criteria": [
                        {"name": "helpfulness", "description": "Response is helpful", "weight": 1.0},
                    ],
                    "weight": 1.0,
                    "required": False,
                },
            ]
        )

        config = AdapterConfig(model="gpt-4o-mini")

        # Mock agent adapter -- returns simple response via ScenarioRunner
        agent_trace = _make_agent_trace()

        mock_agent_runner = AsyncMock(return_value=agent_trace)

        # Mock judge adapter -- returns scores via tool call
        mock_judge_adapter = MagicMock()
        mock_judge_adapter.provider_name.return_value = "openai"
        mock_judge_adapter.send_turn = AsyncMock(
            return_value=_make_judge_adapter_result(
                {"helpfulness": {"score": 0.9, "reasoning": "Very helpful"}}
            )
        )

        def mock_adapter_factory():
            adapter = MagicMock(spec=BaseAdapter)
            return adapter

        runner = TrialRunner(
            adapter_factory=mock_adapter_factory,
            scenario=scenario,
            config=config,
            n_trials=1,
            max_parallel=1,
            threshold=0.8,
        )

        # Patch ScenarioRunner.run to return our trace
        # Patch judge's get_adapter to return our mock judge adapter
        with patch(
            "salvo.execution.runner.ScenarioRunner"
        ) as mock_sr_cls, patch(
            "salvo.evaluation.evaluators.judge.get_adapter",
            return_value=mock_judge_adapter,
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost",
            return_value=0.001,
        ):
            mock_sr_instance = MagicMock()
            mock_sr_instance.run = mock_agent_runner
            mock_sr_cls.return_value = mock_sr_instance

            # Also patch retry_with_backoff to call the factory directly
            async def mock_retry(coro_factory, **kwargs):
                result = await coro_factory()
                return (result, 0, [])

            with patch(
                "salvo.execution.trial_runner.retry_with_backoff",
                side_effect=mock_retry,
            ):
                suite = await runner.run_all()

        assert suite.trials_total == 1
        trial = suite.trials[0]
        assert trial.status == TrialStatus.passed
        assert len(trial.eval_results) == 1

        judge_result = trial.eval_results[0]
        assert judge_result.assertion_type == "judge"
        assert judge_result.passed is True
        assert judge_result.score > 0.8
        assert judge_result.metadata is not None
        assert judge_result.metadata["judge_model"] == "gpt-4o-mini"


class TestE2EMixedAssertions:
    """Test scenario with both standard JMESPath and judge assertions."""

    @pytest.mark.asyncio
    async def test_e2e_mixed_assertions(self) -> None:
        """Scenario with JMESPath + judge assertions, verify both evaluated correctly."""
        scenario = _make_scenario(
            assertions=[
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
                    "criteria": [
                        {"name": "helpfulness", "description": "Response is helpful", "weight": 1.0},
                    ],
                    "weight": 1.0,
                    "required": False,
                },
            ]
        )

        config = AdapterConfig(model="gpt-4o-mini")
        agent_trace = _make_agent_trace()
        mock_agent_runner = AsyncMock(return_value=agent_trace)

        mock_judge_adapter = MagicMock()
        mock_judge_adapter.provider_name.return_value = "openai"
        mock_judge_adapter.send_turn = AsyncMock(
            return_value=_make_judge_adapter_result(
                {"helpfulness": {"score": 0.85, "reasoning": "Good"}}
            )
        )

        def mock_adapter_factory():
            return MagicMock(spec=BaseAdapter)

        runner = TrialRunner(
            adapter_factory=mock_adapter_factory,
            scenario=scenario,
            config=config,
            n_trials=1,
            max_parallel=1,
            threshold=0.8,
        )

        with patch(
            "salvo.execution.runner.ScenarioRunner"
        ) as mock_sr_cls, patch(
            "salvo.evaluation.evaluators.judge.get_adapter",
            return_value=mock_judge_adapter,
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost",
            return_value=0.001,
        ):
            mock_sr_instance = MagicMock()
            mock_sr_instance.run = mock_agent_runner
            mock_sr_cls.return_value = mock_sr_instance

            async def mock_retry(coro_factory, **kwargs):
                result = await coro_factory()
                return (result, 0, [])

            with patch(
                "salvo.execution.trial_runner.retry_with_backoff",
                side_effect=mock_retry,
            ):
                suite = await runner.run_all()

        assert suite.trials_total == 1
        trial = suite.trials[0]
        assert len(trial.eval_results) == 2

        jmespath_result = trial.eval_results[0]
        assert jmespath_result.assertion_type == "jmespath"
        assert jmespath_result.passed is True

        judge_result = trial.eval_results[1]
        assert judge_result.assertion_type == "judge"
        assert judge_result.passed is True

        # Both pass so weighted score should be high
        assert suite.score_avg > 0.8
        assert suite.verdict.value == "PASS"


class TestE2EJudgeCostTracked:
    """Test that judge costs are tracked in the TrialSuiteResult."""

    @pytest.mark.asyncio
    async def test_e2e_judge_cost_tracked_in_suite(self) -> None:
        """Verify judge_cost_total populated in TrialSuiteResult."""
        scenario = _make_scenario(
            assertions=[
                {
                    "type": "judge",
                    "criteria": [
                        {"name": "accuracy", "description": "Factually correct", "weight": 1.0},
                    ],
                    "weight": 1.0,
                    "required": False,
                },
            ]
        )

        config = AdapterConfig(model="gpt-4o-mini")
        agent_trace = _make_agent_trace()
        mock_agent_runner = AsyncMock(return_value=agent_trace)

        mock_judge_adapter = MagicMock()
        mock_judge_adapter.provider_name.return_value = "openai"
        mock_judge_adapter.send_turn = AsyncMock(
            return_value=_make_judge_adapter_result(
                {"accuracy": {"score": 0.9, "reasoning": "Accurate"}}
            )
        )

        def mock_adapter_factory():
            return MagicMock(spec=BaseAdapter)

        runner = TrialRunner(
            adapter_factory=mock_adapter_factory,
            scenario=scenario,
            config=config,
            n_trials=2,
            max_parallel=1,
            threshold=0.8,
        )

        with patch(
            "salvo.execution.runner.ScenarioRunner"
        ) as mock_sr_cls, patch(
            "salvo.evaluation.evaluators.judge.get_adapter",
            return_value=mock_judge_adapter,
        ), patch(
            "salvo.evaluation.evaluators.judge.estimate_cost",
            return_value=0.001,
        ):
            mock_sr_instance = MagicMock()
            mock_sr_instance.run = mock_agent_runner
            mock_sr_cls.return_value = mock_sr_instance

            async def mock_retry(coro_factory, **kwargs):
                result = await coro_factory()
                return (result, 0, [])

            with patch(
                "salvo.execution.trial_runner.retry_with_backoff",
                side_effect=mock_retry,
            ):
                suite = await runner.run_all()

        # 2 trials * 3 judge calls each * $0.001/call = $0.006 total judge cost
        assert suite.judge_cost_total is not None
        assert suite.judge_cost_total == pytest.approx(0.006, abs=1e-6)

        # Verify individual trial eval results have metadata
        for trial in suite.trials:
            for er in trial.eval_results:
                if er.assertion_type == "judge":
                    assert er.metadata is not None
                    assert "judge_cost_usd" in er.metadata
