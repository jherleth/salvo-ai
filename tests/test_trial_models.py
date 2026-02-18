"""Tests for salvo.models.trial - TrialResult, TrialSuiteResult, Verdict, TrialStatus."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from salvo.models.result import EvalResult
from salvo.models.trial import (
    TrialResult,
    TrialStatus,
    TrialSuiteResult,
    Verdict,
)


def _make_trial_result(**overrides) -> TrialResult:
    """Create a minimal TrialResult with defaults."""
    defaults = {
        "trial_number": 1,
        "status": TrialStatus.passed,
        "score": 1.0,
        "passed": True,
        "latency_seconds": 0.5,
    }
    defaults.update(overrides)
    return TrialResult(**defaults)


def _make_suite_result(**overrides) -> TrialSuiteResult:
    """Create a minimal TrialSuiteResult with defaults."""
    trial = _make_trial_result()
    defaults = {
        "run_id": "test-run-001",
        "scenario_name": "test-scenario",
        "scenario_file": "scenarios/test.yaml",
        "model": "gpt-4o",
        "adapter": "openai",
        "trials": [trial],
        "trials_total": 1,
        "trials_passed": 1,
        "trials_failed": 0,
        "trials_hard_fail": 0,
        "trials_infra_error": 0,
        "verdict": Verdict.PASS,
        "pass_rate": 1.0,
        "score_avg": 1.0,
        "score_min": 1.0,
        "score_p50": 1.0,
        "score_p95": 1.0,
        "threshold": 0.8,
    }
    defaults.update(overrides)
    return TrialSuiteResult(**defaults)


class TestTrialStatus:
    """Test TrialStatus enum values."""

    def test_all_values_present(self):
        assert TrialStatus.passed == "passed"
        assert TrialStatus.failed == "failed"
        assert TrialStatus.hard_fail == "hard_fail"
        assert TrialStatus.infra_error == "infra_error"

    def test_string_representation(self):
        # TrialStatus is a str enum, so .value gives the string
        assert TrialStatus.passed.value == "passed"
        assert TrialStatus.infra_error.value == "infra_error"


class TestTrialResult:
    """Test TrialResult model."""

    def test_creation_with_required_fields(self):
        result = _make_trial_result()
        assert result.trial_number == 1
        assert result.status == TrialStatus.passed
        assert result.score == 1.0
        assert result.passed is True
        assert result.latency_seconds == 0.5

    def test_defaults_for_optional_fields(self):
        result = _make_trial_result()
        assert result.eval_results == []
        assert result.cost_usd is None
        assert result.retries_used == 0
        assert result.transient_error_types == []
        assert result.error_message is None
        assert result.trace_id is None

    def test_with_eval_results(self):
        er = EvalResult(
            assertion_type="jmespath",
            score=0.5,
            passed=False,
            weight=2.0,
            required=False,
            details="score mismatch",
        )
        result = _make_trial_result(eval_results=[er])
        assert len(result.eval_results) == 1
        assert result.eval_results[0].assertion_type == "jmespath"

    def test_infra_error_with_message(self):
        result = _make_trial_result(
            status=TrialStatus.infra_error,
            score=0.0,
            passed=False,
            error_message="Connection timed out",
            retries_used=3,
            transient_error_types=["TimeoutError", "TimeoutError", "TimeoutError"],
        )
        assert result.status == TrialStatus.infra_error
        assert result.error_message == "Connection timed out"
        assert result.retries_used == 3

    def test_json_round_trip(self):
        er = EvalResult(
            assertion_type="tool_call",
            score=1.0,
            passed=True,
            weight=1.0,
            required=True,
        )
        original = _make_trial_result(
            eval_results=[er],
            cost_usd=0.05,
            trace_id="trace-123",
        )
        json_str = original.model_dump_json()
        restored = TrialResult.model_validate_json(json_str)
        assert restored.trial_number == original.trial_number
        assert restored.status == original.status
        assert restored.score == original.score
        assert restored.cost_usd == original.cost_usd
        assert restored.trace_id == original.trace_id
        assert len(restored.eval_results) == 1

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            TrialResult(
                trial_number=1,
                status=TrialStatus.passed,
                score=1.0,
                passed=True,
                latency_seconds=0.5,
                unknown_field="bad",
            )


class TestVerdict:
    """Test Verdict enum values."""

    def test_all_values_present(self):
        assert Verdict.PASS == "PASS"
        assert Verdict.FAIL == "FAIL"
        assert Verdict.HARD_FAIL == "HARD FAIL"
        assert Verdict.PARTIAL == "PARTIAL"
        assert Verdict.INFRA_ERROR == "INFRA_ERROR"


class TestTrialSuiteResult:
    """Test TrialSuiteResult model."""

    def test_creation_with_defaults(self):
        suite = _make_suite_result()
        assert suite.run_id == "test-run-001"
        assert suite.scenario_name == "test-scenario"
        assert suite.verdict == Verdict.PASS
        assert suite.pass_rate == 1.0
        assert len(suite.trials) == 1

    def test_optional_fields_default(self):
        suite = _make_suite_result()
        assert suite.cost_total is None
        assert suite.cost_avg_per_trial is None
        assert suite.latency_p50 is None
        assert suite.latency_p95 is None
        assert suite.total_retries == 0
        assert suite.trials_with_retries == 0
        assert suite.early_stopped is False
        assert suite.early_stop_reason is None
        assert suite.n_requested == 3
        assert suite.assertion_failures == []

    def test_json_round_trip(self):
        suite = _make_suite_result(
            cost_total=0.15,
            cost_avg_per_trial=0.15,
            latency_p50=0.5,
            latency_p95=0.8,
            total_retries=2,
            trials_with_retries=1,
        )
        json_str = suite.model_dump_json()
        restored = TrialSuiteResult.model_validate_json(json_str)
        assert restored.run_id == suite.run_id
        assert restored.verdict == suite.verdict
        assert restored.cost_total == suite.cost_total
        assert restored.latency_p50 == suite.latency_p50
        assert len(restored.trials) == 1

    def test_extra_fields_rejected(self):
        trial = _make_trial_result()
        with pytest.raises(ValidationError, match="extra"):
            TrialSuiteResult(
                run_id="r1",
                scenario_name="s",
                scenario_file="f",
                model="m",
                adapter="a",
                trials=[trial],
                trials_total=1,
                trials_passed=1,
                trials_failed=0,
                trials_hard_fail=0,
                trials_infra_error=0,
                verdict=Verdict.PASS,
                pass_rate=1.0,
                score_avg=1.0,
                score_min=1.0,
                score_p50=1.0,
                score_p95=1.0,
                threshold=0.8,
                bogus="nope",
            )

    def test_multiple_trials(self):
        trials = [
            _make_trial_result(trial_number=i, score=0.8 if i % 2 == 0 else 0.2, passed=i % 2 == 0)
            for i in range(5)
        ]
        suite = _make_suite_result(
            trials=trials,
            trials_total=5,
            trials_passed=3,
            trials_failed=2,
            pass_rate=0.6,
            score_avg=0.56,
            score_min=0.2,
            score_p50=0.8,
            score_p95=0.8,
        )
        assert suite.trials_total == 5
        assert suite.trials_passed == 3
        assert len(suite.trials) == 5

    def test_early_stop_fields(self):
        suite = _make_suite_result(
            early_stopped=True,
            early_stop_reason="Hard fail detected on trial 1",
        )
        assert suite.early_stopped is True
        assert suite.early_stop_reason == "Hard fail detected on trial 1"

    def test_assertion_failures_field(self):
        failures = [
            {
                "assertion_type": "jmespath",
                "expression": "response.status",
                "fail_count": 3,
                "fail_rate": 0.6,
                "total_weight_lost": 1.5,
                "sample_details": ["expected ok, got error"],
            }
        ]
        suite = _make_suite_result(assertion_failures=failures)
        assert len(suite.assertion_failures) == 1
        assert suite.assertion_failures[0]["fail_count"] == 3
