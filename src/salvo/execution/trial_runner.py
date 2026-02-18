"""TrialRunner: N-trial execution engine with isolation, concurrency, and early-stop.

Orchestrates running a scenario N times, each in an isolated temporary
directory with a fresh adapter instance. Supports concurrent execution
via asyncio.Semaphore + TaskGroup and early-stop on hard fail or
mathematical impossibility.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from salvo.adapters.base import AdapterConfig, BaseAdapter
from salvo.evaluation.aggregation import (
    aggregate_failures,
    compute_aggregate_metrics,
    determine_verdict,
)
from salvo.evaluation.scorer import evaluate_trace
from salvo.execution.retry import retry_with_backoff
from salvo.models.result import EvalResult
from salvo.models.scenario import Scenario
from salvo.models.trial import TrialResult, TrialStatus, TrialSuiteResult


class TrialRunner:
    """Orchestrates N-trial execution of a scenario.

    Each trial runs in an isolated temporary directory with a fresh
    adapter instance created via adapter_factory. Supports sequential
    and concurrent modes, retry on transient errors, and early-stop.
    """

    def __init__(
        self,
        adapter_factory: Callable[[], BaseAdapter],
        scenario: Scenario,
        config: AdapterConfig,
        n_trials: int = 3,
        max_parallel: int = 1,
        max_retries: int = 3,
        early_stop: bool = False,
        threshold: float = 1.0,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._scenario = scenario
        self._config = config
        self._n_trials = n_trials
        self._max_parallel = max_parallel
        self._max_retries = max_retries
        self._early_stop = early_stop
        self._threshold = threshold

    async def run_all(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> TrialSuiteResult:
        """Execute all trials and return aggregate results.

        Args:
            progress_callback: Optional callback(trial_num, total) called
                after each trial completes.

        Returns:
            TrialSuiteResult with all individual results and aggregate metrics.
        """
        if self._max_parallel <= 1:
            results = await self._run_sequential(progress_callback)
        else:
            results = await self._run_concurrent(progress_callback)

        return self._build_suite_result(results)

    async def _run_sequential(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[TrialResult]:
        """Execute trials one at a time, checking early-stop after each."""
        results: list[TrialResult] = []

        for trial_num in range(1, self._n_trials + 1):
            result = await self._execute_single_trial(trial_num)
            results.append(result)

            if progress_callback is not None:
                progress_callback(trial_num, self._n_trials)

            if self._early_stop and self._should_stop_early(results):
                break

        return results

    async def _run_concurrent(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[TrialResult]:
        """Execute trials concurrently with bounded parallelism."""
        semaphore = asyncio.Semaphore(self._max_parallel)
        stop_event = asyncio.Event()
        results: list[TrialResult | None] = [None] * self._n_trials
        lock = asyncio.Lock()

        async def run_one(trial_num: int) -> None:
            if stop_event.is_set():
                return

            async with semaphore:
                if stop_event.is_set():
                    return

                result = await self._execute_single_trial(trial_num)

                async with lock:
                    results[trial_num - 1] = result

                    if progress_callback is not None:
                        progress_callback(trial_num, self._n_trials)

                    if self._early_stop:
                        completed = [r for r in results if r is not None]
                        if self._should_stop_early(completed):
                            stop_event.set()

        async with asyncio.TaskGroup() as tg:
            for trial_num in range(1, self._n_trials + 1):
                tg.create_task(run_one(trial_num))

        # Filter out None entries (skipped due to early-stop)
        return [r for r in results if r is not None]

    async def _execute_single_trial(self, trial_num: int) -> TrialResult:
        """Execute a single trial with isolation, retry, and evaluation.

        Creates a unique temporary directory and fresh adapter per trial.
        Wraps execution in retry_with_backoff for transient error handling.
        """
        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix=f"salvo_trial_{trial_num}_") as tmpdir:
            adapter = self._adapter_factory()

            from salvo.execution.runner import ScenarioRunner

            runner = ScenarioRunner(adapter)

            try:
                trace, retries_used, error_types = await retry_with_backoff(
                    coro_factory=lambda: runner.run(self._scenario, self._config),
                    max_retries=self._max_retries,
                    base_delay=1.0,
                    max_delay=30.0,
                )

                # Normalize assertions for evaluation
                raw_assertions = [
                    a.model_dump(exclude_none=True)
                    for a in self._scenario.assertions
                ]

                eval_results, score, passed = evaluate_trace(
                    trace, raw_assertions, self._threshold,
                )

                # Determine trial status
                hard_fail = any(
                    r.required and not r.passed for r in eval_results
                )
                if hard_fail:
                    status = TrialStatus.hard_fail
                elif passed:
                    status = TrialStatus.passed
                else:
                    status = TrialStatus.failed

                elapsed = time.perf_counter() - start_time

                return TrialResult(
                    trial_number=trial_num,
                    status=status,
                    score=score,
                    passed=passed,
                    eval_results=eval_results,
                    latency_seconds=elapsed,
                    cost_usd=trace.cost_usd,
                    retries_used=retries_used,
                    transient_error_types=error_types,
                    trace_id=None,  # Assigned by RunStore later
                )

            except Exception as exc:
                elapsed = time.perf_counter() - start_time
                return TrialResult(
                    trial_number=trial_num,
                    status=TrialStatus.infra_error,
                    score=0.0,
                    passed=False,
                    latency_seconds=elapsed,
                    error_message=str(exc),
                    retries_used=self._max_retries,
                    transient_error_types=[type(exc).__name__],
                )

    def _should_stop_early(self, completed: list[TrialResult]) -> bool:
        """Check if remaining trials cannot change the outcome.

        Stops if:
        1. Any trial had a hard fail.
        2. Even if all remaining trials score 1.0, the average cannot
           reach the threshold.
        """
        if any(r.status == TrialStatus.hard_fail for r in completed):
            return True

        n_completed = len(completed)
        n_remaining = self._n_trials - n_completed
        if n_remaining <= 0:
            return False

        current_score_sum = sum(r.score for r in completed)
        # Pessimistic: assume all remaining score 1.0
        best_possible_avg = (current_score_sum + n_remaining * 1.0) / self._n_trials

        return best_possible_avg < self._threshold

    def _build_suite_result(self, results: list[TrialResult]) -> TrialSuiteResult:
        """Build the final TrialSuiteResult from individual trial results."""
        # Separate scored trials (exclude infra errors for metric computation)
        scored_trials = [
            r for r in results if r.status != TrialStatus.infra_error
        ]

        metrics = compute_aggregate_metrics(scored_trials, self._threshold)
        verdict = determine_verdict(
            results, metrics["score_avg"], self._threshold,
        )
        failures = aggregate_failures(results)

        # Count by status
        n_passed = sum(1 for r in results if r.status == TrialStatus.passed)
        n_failed = sum(1 for r in results if r.status == TrialStatus.failed)
        n_hard_fail = sum(1 for r in results if r.status == TrialStatus.hard_fail)
        n_infra = sum(1 for r in results if r.status == TrialStatus.infra_error)

        # Retry stats
        total_retries = sum(r.retries_used for r in results)
        trials_with_retries = sum(1 for r in results if r.retries_used > 0)

        # Early-stop detection
        early_stopped = len(results) < self._n_trials
        early_stop_reason: str | None = None
        if early_stopped:
            if any(r.status == TrialStatus.hard_fail for r in results):
                early_stop_reason = (
                    f"Hard fail detected on trial {next(r.trial_number for r in results if r.status == TrialStatus.hard_fail)}"
                )
            else:
                early_stop_reason = "Threshold mathematically unreachable"

        run_id = str(uuid.uuid7())

        return TrialSuiteResult(
            run_id=run_id,
            scenario_name=self._scenario.description or self._scenario.prompt[:50],
            scenario_file="",  # Set by caller
            model=self._config.model,
            adapter=self._scenario.adapter,
            trials=results,
            trials_total=len(results),
            trials_passed=n_passed,
            trials_failed=n_failed,
            trials_hard_fail=n_hard_fail,
            trials_infra_error=n_infra,
            verdict=verdict,
            pass_rate=metrics["pass_rate"],
            score_avg=metrics["score_avg"],
            score_min=metrics["score_min"],
            score_p50=metrics["score_p50"],
            score_p95=metrics["score_p95"],
            threshold=self._threshold,
            cost_total=metrics["cost_total"],
            cost_avg_per_trial=metrics["cost_avg_per_trial"],
            latency_p50=metrics["latency_p50"],
            latency_p95=metrics["latency_p95"],
            total_retries=total_retries,
            trials_with_retries=trials_with_retries,
            early_stopped=early_stopped,
            early_stop_reason=early_stop_reason,
            n_requested=self._n_trials,
            assertion_failures=failures,
        )
