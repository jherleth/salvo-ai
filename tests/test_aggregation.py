"""Tests for salvo.evaluation.aggregation - metrics, verdict, failure ranking."""

from __future__ import annotations

import pytest

from salvo.evaluation.aggregation import (
    aggregate_failures,
    compute_aggregate_metrics,
    determine_verdict,
)
from salvo.models.result import EvalResult
from salvo.models.trial import TrialResult, TrialStatus, Verdict


def _make_trial(
    trial_number: int = 1,
    status: TrialStatus = TrialStatus.passed,
    score: float = 1.0,
    passed: bool = True,
    latency: float = 1.0,
    cost: float | None = 0.01,
    eval_results: list[EvalResult] | None = None,
    retries: int = 0,
) -> TrialResult:
    """Create a TrialResult for testing."""
    return TrialResult(
        trial_number=trial_number,
        status=status,
        score=score,
        passed=passed,
        latency_seconds=latency,
        cost_usd=cost,
        eval_results=eval_results or [],
        retries_used=retries,
    )


class TestComputeAggregateMetrics:
    """Test compute_aggregate_metrics function."""

    def test_zero_trials(self):
        result = compute_aggregate_metrics([], threshold=0.8)
        assert result["score_avg"] == 0.0
        assert result["score_min"] == 0.0
        assert result["score_p50"] == 0.0
        assert result["score_p95"] == 0.0
        assert result["pass_rate"] == 0.0
        assert result["latency_p50"] is None
        assert result["latency_p95"] is None
        assert result["cost_total"] is None
        assert result["cost_avg_per_trial"] is None

    def test_single_trial(self):
        trial = _make_trial(score=0.9, passed=True, latency=2.5, cost=0.05)
        result = compute_aggregate_metrics([trial], threshold=0.8)
        assert result["score_avg"] == 0.9
        assert result["score_min"] == 0.9
        assert result["score_p50"] == 0.9
        assert result["score_p95"] == 0.9
        assert result["pass_rate"] == 1.0
        assert result["latency_p50"] == 2.5
        assert result["latency_p95"] == 2.5
        assert result["cost_total"] == 0.05
        assert result["cost_avg_per_trial"] == 0.05

    def test_two_trials(self):
        trials = [
            _make_trial(trial_number=1, score=0.8, passed=True, latency=1.0, cost=0.01),
            _make_trial(trial_number=2, score=0.6, passed=False, latency=2.0, cost=0.02),
        ]
        result = compute_aggregate_metrics(trials, threshold=0.8)
        assert result["score_avg"] == pytest.approx(0.7)
        assert result["score_min"] == 0.6
        assert result["pass_rate"] == 0.5
        assert result["cost_total"] == pytest.approx(0.03)
        assert result["cost_avg_per_trial"] == pytest.approx(0.015)

    def test_ten_trials_percentiles(self):
        """10 trials with scores 0.1 to 1.0 - verify percentile ordering."""
        trials = [
            _make_trial(
                trial_number=i + 1,
                score=round((i + 1) * 0.1, 1),
                passed=(i + 1) * 0.1 >= 0.8,
                latency=float(i + 1),
                cost=0.01,
            )
            for i in range(10)
        ]
        result = compute_aggregate_metrics(trials, threshold=0.8)
        assert result["score_avg"] == pytest.approx(0.55)
        assert result["score_min"] == 0.1
        # p50 should be around the median
        assert result["score_p50"] >= 0.4
        assert result["score_p50"] <= 0.7
        # p95 should be high
        assert result["score_p95"] >= 0.9
        assert result["pass_rate"] == 0.3  # 0.8, 0.9, 1.0 pass

    def test_no_costs(self):
        """Trials with no cost data."""
        trials = [
            _make_trial(trial_number=1, cost=None),
            _make_trial(trial_number=2, cost=None),
        ]
        result = compute_aggregate_metrics(trials, threshold=0.8)
        assert result["cost_total"] is None
        assert result["cost_avg_per_trial"] is None

    def test_mixed_costs(self):
        """Some trials have cost, some do not."""
        trials = [
            _make_trial(trial_number=1, cost=0.05),
            _make_trial(trial_number=2, cost=None),
            _make_trial(trial_number=3, cost=0.03),
        ]
        result = compute_aggregate_metrics(trials, threshold=0.8)
        assert result["cost_total"] == pytest.approx(0.08)
        # avg computed over all trials (3), not just those with costs
        assert result["cost_avg_per_trial"] == pytest.approx(0.08 / 3)


class TestDetermineVerdict:
    """Test determine_verdict function."""

    def test_pass_verdict(self):
        trials = [_make_trial(score=0.9, passed=True) for _ in range(3)]
        verdict = determine_verdict(trials, avg_score=0.9, threshold=0.8)
        assert verdict == Verdict.PASS

    def test_fail_verdict_all_fail(self):
        trials = [
            _make_trial(status=TrialStatus.failed, score=0.3, passed=False)
            for _ in range(3)
        ]
        verdict = determine_verdict(trials, avg_score=0.3, threshold=0.8)
        assert verdict == Verdict.FAIL

    def test_hard_fail_verdict(self):
        trials = [
            _make_trial(status=TrialStatus.hard_fail, score=0.0, passed=False),
            _make_trial(score=1.0, passed=True),
        ]
        verdict = determine_verdict(trials, avg_score=0.5, threshold=0.8)
        assert verdict == Verdict.HARD_FAIL

    def test_partial_verdict(self):
        """Some pass, some fail, avg below threshold."""
        trials = [
            _make_trial(trial_number=1, score=1.0, passed=True),
            _make_trial(trial_number=2, status=TrialStatus.failed, score=0.2, passed=False),
            _make_trial(trial_number=3, status=TrialStatus.failed, score=0.1, passed=False),
        ]
        verdict = determine_verdict(trials, avg_score=0.43, threshold=0.8)
        assert verdict == Verdict.PARTIAL

    def test_infra_error_verdict(self):
        trials = [
            _make_trial(status=TrialStatus.infra_error, score=0.0, passed=False),
            _make_trial(score=1.0, passed=True),
        ]
        verdict = determine_verdict(trials, avg_score=0.5, threshold=0.8)
        assert verdict == Verdict.INFRA_ERROR

    def test_infra_error_allowed(self):
        """allow_infra=True ignores INFRA_ERROR trials."""
        trials = [
            _make_trial(status=TrialStatus.infra_error, score=0.0, passed=False),
            _make_trial(score=1.0, passed=True),
            _make_trial(score=0.9, passed=True),
        ]
        verdict = determine_verdict(
            trials, avg_score=0.95, threshold=0.8, allow_infra=True,
        )
        assert verdict == Verdict.PASS

    def test_all_infra_error(self):
        trials = [
            _make_trial(
                trial_number=i,
                status=TrialStatus.infra_error,
                score=0.0,
                passed=False,
            )
            for i in range(3)
        ]
        verdict = determine_verdict(trials, avg_score=0.0, threshold=0.8)
        assert verdict == Verdict.INFRA_ERROR


class TestAggregateFailures:
    """Test aggregate_failures function."""

    def test_empty_trials(self):
        result = aggregate_failures([])
        assert result == []

    def test_all_passing(self):
        """No failures when all assertions pass."""
        er = EvalResult(
            assertion_type="jmespath",
            score=1.0,
            passed=True,
            weight=1.0,
            required=False,
            details="ok",
        )
        trials = [_make_trial(eval_results=[er]) for _ in range(3)]
        result = aggregate_failures(trials)
        assert result == []

    def test_single_failure_type(self):
        """Same assertion fails across multiple trials."""
        failing_er = EvalResult(
            assertion_type="jmespath",
            score=0.0,
            passed=False,
            weight=2.0,
            required=False,
            details="expected 'ok', got 'error'",
        )
        passing_er = EvalResult(
            assertion_type="jmespath",
            score=1.0,
            passed=True,
            weight=2.0,
            required=False,
            details="expected 'ok', got 'ok'",
        )

        trials = [
            _make_trial(trial_number=1, eval_results=[failing_er]),
            _make_trial(trial_number=2, eval_results=[failing_er]),
            _make_trial(trial_number=3, eval_results=[passing_er]),
        ]
        result = aggregate_failures(trials)

        assert len(result) == 1
        entry = result[0]
        assert entry["assertion_type"] == "jmespath"
        assert entry["fail_count"] == 2
        assert entry["fail_rate"] == pytest.approx(2 / 3)
        assert entry["total_weight_lost"] == pytest.approx(4.0)  # (1-0)*2 * 2 fails

    def test_ranking_by_impact(self):
        """Higher frequency * weight_lost ranks first."""
        # High frequency, low weight
        low_weight_fail = EvalResult(
            assertion_type="tool_call",
            score=0.0,
            passed=False,
            weight=1.0,
            required=False,
            details="tool not called",
        )
        # Low frequency, high weight
        high_weight_fail = EvalResult(
            assertion_type="jmespath",
            score=0.0,
            passed=False,
            weight=10.0,
            required=True,
            details="response.status check failed",
        )

        trials = [
            _make_trial(trial_number=1, eval_results=[low_weight_fail]),
            _make_trial(trial_number=2, eval_results=[low_weight_fail]),
            _make_trial(trial_number=3, eval_results=[low_weight_fail]),
            _make_trial(trial_number=4, eval_results=[high_weight_fail]),
        ]

        result = aggregate_failures(trials)
        assert len(result) == 2

        # low_weight_fail: count=3, avg_weight_lost=1.0, impact=3*1=3
        # high_weight_fail: count=1, avg_weight_lost=10.0, impact=1*10=10
        # high_weight_fail should rank first (impact 10 > 3)
        assert result[0]["assertion_type"] == "jmespath"
        assert result[1]["assertion_type"] == "tool_call"

    def test_sample_details_capped_at_3(self):
        """sample_details collects at most 3 examples."""
        failing_er = EvalResult(
            assertion_type="jmespath",
            score=0.0,
            passed=False,
            weight=1.0,
            required=False,
            details="failed check",
        )
        trials = [
            _make_trial(trial_number=i, eval_results=[failing_er])
            for i in range(5)
        ]
        result = aggregate_failures(trials)
        assert len(result) == 1
        assert len(result[0]["sample_details"]) == 3

    def test_expression_truncated_at_80_chars(self):
        """Long details strings are truncated to 80 chars for grouping key."""
        long_detail = "x" * 200
        failing_er = EvalResult(
            assertion_type="jmespath",
            score=0.0,
            passed=False,
            weight=1.0,
            required=False,
            details=long_detail,
        )
        trials = [_make_trial(eval_results=[failing_er])]
        result = aggregate_failures(trials)
        assert len(result[0]["expression"]) == 80

    def test_mixed_pass_fail_assertions(self):
        """Trial with both passing and failing assertions."""
        pass_er = EvalResult(
            assertion_type="tool_call",
            score=1.0,
            passed=True,
            weight=1.0,
            required=False,
            details="tool called",
        )
        fail_er = EvalResult(
            assertion_type="jmespath",
            score=0.0,
            passed=False,
            weight=2.0,
            required=False,
            details="check failed",
        )
        trials = [_make_trial(eval_results=[pass_er, fail_er])]
        result = aggregate_failures(trials)
        # Only the failing assertion should appear
        assert len(result) == 1
        assert result[0]["assertion_type"] == "jmespath"
