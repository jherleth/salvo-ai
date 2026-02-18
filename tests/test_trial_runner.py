"""Tests for salvo.execution.trial_runner - TrialRunner orchestration."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)
from salvo.execution.trial_runner import TrialRunner
from salvo.models.scenario import Assertion, Scenario
from salvo.models.trial import TrialStatus, Verdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockTrialAdapter(BaseAdapter):
    """Adapter that returns a pre-configured response on each send_turn.

    Supports raising exceptions to simulate transient errors.
    """

    def __init__(
        self,
        content: str = "Hello from mock",
        raise_on_call: list[Exception] | None = None,
    ) -> None:
        self._content = content
        self._raise_on_call = list(raise_on_call) if raise_on_call else []
        self._call_count = 0

    async def send_turn(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        config: AdapterConfig | None = None,
    ) -> AdapterTurnResult:
        self._call_count += 1
        if self._raise_on_call:
            exc = self._raise_on_call.pop(0)
            raise exc
        return AdapterTurnResult(
            content=self._content,
            tool_calls=[],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_response={},
            finish_reason="stop",
        )

    def provider_name(self) -> str:
        return "MockTrialAdapter"


def _make_scenario(**overrides) -> Scenario:
    """Create a minimal scenario for trial testing."""
    defaults: dict[str, Any] = {
        "model": "gpt-4o",
        "prompt": "Say hello",
        "threshold": 0.8,
    }
    defaults.update(overrides)
    return Scenario(**defaults)


def _make_config(model: str = "gpt-4o") -> AdapterConfig:
    return AdapterConfig(model=model)


def _make_passing_factory() -> tuple[list[MockTrialAdapter], Any]:
    """Create a factory that tracks created adapters and returns passing results."""
    created: list[MockTrialAdapter] = []

    def factory():
        adapter = MockTrialAdapter(content="Hello")
        created.append(adapter)
        return adapter

    return created, factory


def _make_failing_factory(
    raise_exc: Exception | None = None,
) -> tuple[list[MockTrialAdapter], Any]:
    """Create a factory that returns adapters raising errors."""
    created: list[MockTrialAdapter] = []

    def factory():
        adapter = MockTrialAdapter(
            raise_on_call=[raise_exc or TimeoutError("timed out")] * 10,
        )
        created.append(adapter)
        return adapter

    return created, factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTrialRunnerSingleTrial:
    """Test basic single-trial execution."""

    @pytest.mark.asyncio
    async def test_single_trial_pass(self):
        """N=1, adapter returns valid response, no assertions -> PASS."""
        _created, factory = _make_passing_factory()
        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=1,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.verdict == Verdict.PASS
        assert result.trials_total == 1
        assert result.trials_passed == 1
        assert result.pass_rate == 1.0
        assert result.score_avg == 1.0
        assert len(result.trials) == 1
        assert result.trials[0].status == TrialStatus.passed

    @pytest.mark.asyncio
    async def test_single_trial_with_assertions(self):
        """N=1, with a jmespath assertion that passes."""
        _created, factory = _make_passing_factory()
        scenario = _make_scenario(
            assertions=[
                Assertion(
                    type="jmespath",
                    expression="response.content",
                    operator="contains",
                    value="Hello",
                    weight=1.0,
                ),
            ],
        )
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=1,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.verdict == Verdict.PASS
        assert result.trials[0].score == 1.0
        assert len(result.trials[0].eval_results) == 1


class TestTrialRunnerMultipleTrials:
    """Test multiple trial execution."""

    @pytest.mark.asyncio
    async def test_multiple_trials_all_pass(self):
        """N=5, all pass -> PASS with correct counts."""
        _created, factory = _make_passing_factory()
        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=5,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.trials_total == 5
        assert result.trials_passed == 5
        assert result.verdict == Verdict.PASS
        assert result.pass_rate == 1.0
        assert len(_created) == 5  # One adapter per trial


class TestTrialRunnerConcurrent:
    """Test concurrent execution mode."""

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """N=5, max_parallel=3, all 5 complete with correct results."""
        _created, factory = _make_passing_factory()
        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=5,
            max_parallel=3,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.trials_total == 5
        assert result.trials_passed == 5
        assert result.verdict == Verdict.PASS
        # Verify each trial got a unique adapter
        assert len(_created) == 5

    @pytest.mark.asyncio
    async def test_concurrent_same_as_sequential(self):
        """Concurrent mode produces same aggregate results as sequential."""
        scenario = _make_scenario()
        config = _make_config()

        # Sequential
        _created_seq, factory_seq = _make_passing_factory()
        runner_seq = TrialRunner(
            adapter_factory=factory_seq,
            scenario=scenario,
            config=config,
            n_trials=3,
            max_parallel=1,
            threshold=0.8,
        )
        result_seq = await runner_seq.run_all()

        # Concurrent
        _created_par, factory_par = _make_passing_factory()
        runner_par = TrialRunner(
            adapter_factory=factory_par,
            scenario=scenario,
            config=config,
            n_trials=3,
            max_parallel=3,
            threshold=0.8,
        )
        result_par = await runner_par.run_all()

        assert result_seq.verdict == result_par.verdict
        assert result_seq.trials_total == result_par.trials_total
        assert result_seq.pass_rate == result_par.pass_rate


class TestTrialIsolation:
    """Test that each trial gets isolation (unique tmpdir + fresh adapter)."""

    @pytest.mark.asyncio
    async def test_trial_isolation_unique_adapters(self):
        """Each trial creates a unique adapter via factory."""
        created, factory = _make_passing_factory()
        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=3,
            threshold=0.8,
        )
        await runner.run_all()

        # Verify 3 distinct adapter instances
        assert len(created) == 3
        assert len(set(id(a) for a in created)) == 3

    @pytest.mark.asyncio
    async def test_trial_isolation_tmpdir(self):
        """Each trial creates a TemporaryDirectory with unique prefix."""
        tmpdir_names: list[str] = []

        original_init = __import__("tempfile").TemporaryDirectory.__init__

        def tracking_init(self_td, *args, **kwargs):
            original_init(self_td, *args, **kwargs)
            tmpdir_names.append(self_td.name)

        with patch.object(
            __import__("tempfile").TemporaryDirectory,
            "__init__",
            tracking_init,
        ):
            _created, factory = _make_passing_factory()
            scenario = _make_scenario()
            config = _make_config()

            runner = TrialRunner(
                adapter_factory=factory,
                scenario=scenario,
                config=config,
                n_trials=3,
                threshold=0.8,
            )
            await runner.run_all()

        assert len(tmpdir_names) == 3
        # All directories should be unique
        assert len(set(tmpdir_names)) == 3


class TestTrialRunnerRetry:
    """Test retry behavior on transient errors."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Adapter raises TimeoutError first call, succeeds second -> retries_used=1."""
        created: list[MockTrialAdapter] = []

        def factory():
            adapter = MockTrialAdapter(
                content="Hello",
                raise_on_call=[TimeoutError("timed out")],
            )
            created.append(adapter)
            return adapter

        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=1,
            max_retries=3,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.trials[0].retries_used == 1
        assert result.trials[0].transient_error_types == ["TimeoutError"]
        assert result.trials[0].status == TrialStatus.passed
        assert result.total_retries == 1
        assert result.trials_with_retries == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_infra_error(self):
        """Adapter always raises 429 -> trial status=INFRA_ERROR."""
        _created, factory = _make_failing_factory()
        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=1,
            max_retries=3,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.trials[0].status == TrialStatus.infra_error
        assert result.trials[0].error_message is not None
        assert result.verdict == Verdict.INFRA_ERROR


class TestTrialRunnerEarlyStop:
    """Test early-stop behavior."""

    @pytest.mark.asyncio
    async def test_early_stop_on_hard_fail(self):
        """N=10, first trial has hard fail with early_stop -> stops after 1."""
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            # All adapters return content that will fail "required" assertion
            return MockTrialAdapter(content="WRONG ANSWER")

        scenario = _make_scenario(
            assertions=[
                Assertion(
                    type="jmespath",
                    expression="response.content",
                    operator="contains",
                    value="impossible_string_never_found",
                    weight=1.0,
                    required=True,
                ),
            ],
        )
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=10,
            max_parallel=1,
            early_stop=True,
            threshold=0.8,
        )
        result = await runner.run_all()

        # Should stop after first trial (hard fail due to required assertion)
        assert result.early_stopped is True
        assert result.trials_total < 10
        assert result.verdict == Verdict.HARD_FAIL

    @pytest.mark.asyncio
    async def test_early_stop_mathematically_impossible(self):
        """N=10, first trials all score 0.0 with threshold 0.8 -> stops early."""
        def factory():
            # Content that fails assertion -> score 0
            return MockTrialAdapter(content="wrong")

        scenario = _make_scenario(
            assertions=[
                Assertion(
                    type="jmespath",
                    expression="response.content",
                    operator="contains",
                    value="impossible_string_xyz",
                    weight=1.0,
                    required=False,  # Not required, so it's a scored fail not hard fail
                ),
            ],
            threshold=0.8,
        )
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=10,
            max_parallel=1,
            early_stop=True,
            threshold=0.8,
        )
        result = await runner.run_all()

        # After enough 0.0 scores, mathematically impossible to reach 0.8 avg
        assert result.early_stopped is True
        assert result.trials_total < 10
        assert result.early_stop_reason is not None

    @pytest.mark.asyncio
    async def test_no_early_stop_when_disabled(self):
        """N=5, hard fail but early_stop=False -> all 5 run."""
        def factory():
            return MockTrialAdapter(content="WRONG ANSWER")

        scenario = _make_scenario(
            assertions=[
                Assertion(
                    type="jmespath",
                    expression="response.content",
                    operator="contains",
                    value="impossible_string_never_found",
                    weight=1.0,
                    required=True,
                ),
            ],
        )
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=5,
            max_parallel=1,
            early_stop=False,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.trials_total == 5
        assert result.early_stopped is False


class TestTrialRunnerProgressCallback:
    """Test progress callback invocation."""

    @pytest.mark.asyncio
    async def test_progress_callback_called(self):
        """Callback invoked once per trial with (trial_num, total)."""
        _created, factory = _make_passing_factory()
        scenario = _make_scenario()
        config = _make_config()

        calls: list[tuple[int, int]] = []

        def on_progress(trial_num: int, total: int) -> None:
            calls.append((trial_num, total))

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=3,
            threshold=0.8,
        )
        await runner.run_all(progress_callback=on_progress)

        assert len(calls) == 3
        assert calls[0] == (1, 3)
        assert calls[1] == (2, 3)
        assert calls[2] == (3, 3)


class TestTrialRunnerAllInfraError:
    """Test all trials failing with infra errors."""

    @pytest.mark.asyncio
    async def test_all_infra_error(self):
        """All trials fail with infra errors -> INFRA_ERROR, zeroed metrics."""
        _created, factory = _make_failing_factory()
        scenario = _make_scenario()
        config = _make_config()

        runner = TrialRunner(
            adapter_factory=factory,
            scenario=scenario,
            config=config,
            n_trials=3,
            max_retries=0,
            threshold=0.8,
        )
        result = await runner.run_all()

        assert result.verdict == Verdict.INFRA_ERROR
        assert result.trials_infra_error == 3
        assert result.trials_passed == 0
        assert result.score_avg == 0.0
        assert result.pass_rate == 0.0
