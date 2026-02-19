"""Tests for salvo.cli.report_cmd -- report command with detail, history, and filtering."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from salvo.cli.main import app
from salvo.models.trial import (
    TrialResult,
    TrialStatus,
    TrialSuiteResult,
    Verdict,
)
from salvo.storage.json_store import RunStore


runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suite(
    run_id: str = "test-run-001",
    scenario_name: str = "test-scenario",
    verdict: Verdict = Verdict.PASS,
    trials_total: int = 3,
    trials_passed: int = 3,
    trials_failed: int = 0,
    trials_hard_fail: int = 0,
    trials_infra_error: int = 0,
    pass_rate: float = 1.0,
    score_avg: float = 1.0,
    score_min: float = 1.0,
    score_p50: float = 1.0,
    score_p95: float = 1.0,
    threshold: float = 0.8,
    cost_total: float | None = 0.03,
    cost_avg_per_trial: float | None = 0.01,
    latency_p50: float | None = 1.5,
    latency_p95: float | None = 2.0,
    assertion_failures: list[dict] | None = None,
) -> TrialSuiteResult:
    """Create a minimal TrialSuiteResult for testing."""
    trials = []
    for i in range(trials_passed):
        trials.append(
            TrialResult(
                trial_number=i + 1,
                status=TrialStatus.passed,
                score=score_avg,
                passed=True,
                latency_seconds=1.5,
                cost_usd=0.01,
            )
        )
    for i in range(trials_failed):
        trials.append(
            TrialResult(
                trial_number=trials_passed + i + 1,
                status=TrialStatus.failed,
                score=0.3,
                passed=False,
                latency_seconds=1.5,
                cost_usd=0.01,
            )
        )
    for i in range(trials_hard_fail):
        trials.append(
            TrialResult(
                trial_number=trials_passed + trials_failed + i + 1,
                status=TrialStatus.hard_fail,
                score=0.0,
                passed=False,
                latency_seconds=1.5,
            )
        )
    for i in range(trials_infra_error):
        trials.append(
            TrialResult(
                trial_number=trials_passed + trials_failed + trials_hard_fail + i + 1,
                status=TrialStatus.infra_error,
                score=0.0,
                passed=False,
                latency_seconds=0.5,
                error_message="Connection refused",
            )
        )

    return TrialSuiteResult(
        run_id=run_id,
        scenario_name=scenario_name,
        scenario_file="test.yaml",
        model="gpt-4o",
        adapter="openai",
        trials=trials,
        trials_total=trials_total,
        trials_passed=trials_passed,
        trials_failed=trials_failed,
        trials_hard_fail=trials_hard_fail,
        trials_infra_error=trials_infra_error,
        verdict=verdict,
        pass_rate=pass_rate,
        score_avg=score_avg,
        score_min=score_min,
        score_p50=score_p50,
        score_p95=score_p95,
        threshold=threshold,
        cost_total=cost_total,
        cost_avg_per_trial=cost_avg_per_trial,
        latency_p50=latency_p50,
        latency_p95=latency_p95,
        assertion_failures=assertion_failures or [],
    )


def _setup_store(tmp_path: Path) -> RunStore:
    """Create a RunStore rooted at tmp_path with .salvo/ initialized."""
    store = RunStore(tmp_path)
    store.ensure_dirs()
    return store


# ---------------------------------------------------------------------------
# Tests: Default mode (latest run detail)
# ---------------------------------------------------------------------------


class TestReportLatest:
    """Test default report showing latest run detail."""

    def test_report_latest(self, tmp_path: Path):
        """Report with no args shows the latest run's detail."""
        store = _setup_store(tmp_path)
        suite = _make_suite(run_id="latest-001", scenario_name="booking-agent")
        store.save_suite_result(suite)
        store.update_latest_symlink("latest-001")

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report"])

        assert result.exit_code == 0
        assert "booking-agent" in result.output
        assert "PASS" in result.output
        assert "latest-001" in result.output

    def test_report_by_run_id(self, tmp_path: Path):
        """Report with specific run_id shows that run."""
        store = _setup_store(tmp_path)

        suite1 = _make_suite(run_id="run-aaa", scenario_name="scenario-a")
        suite2 = _make_suite(
            run_id="run-bbb",
            scenario_name="scenario-b",
            verdict=Verdict.FAIL,
            trials_passed=1,
            trials_failed=2,
            trials_total=3,
            pass_rate=0.33,
            score_avg=0.5,
        )
        store.save_suite_result(suite1)
        store.save_suite_result(suite2)
        store.update_latest_symlink("run-bbb")

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "run-aaa"])

        assert result.exit_code == 0
        assert "scenario-a" in result.output
        assert "run-aaa" in result.output

    def test_report_no_runs(self, tmp_path: Path):
        """Report with empty store shows helpful message."""
        _setup_store(tmp_path)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report"])

        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_report_run_id_not_found(self, tmp_path: Path):
        """Report with nonexistent run_id shows error."""
        store = _setup_store(tmp_path)
        suite = _make_suite(run_id="existing-run")
        store.save_suite_result(suite)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# Tests: History mode
# ---------------------------------------------------------------------------


class TestReportHistory:
    """Test --history trend view."""

    def test_report_history(self, tmp_path: Path):
        """History mode shows trend table with all saved runs."""
        store = _setup_store(tmp_path)

        for i in range(3):
            suite = _make_suite(
                run_id=f"hist-{i:03d}",
                scenario_name="multi-run",
                score_avg=0.7 + i * 0.1,
            )
            store.save_suite_result(suite)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "--history"])

        assert result.exit_code == 0
        assert "hist-000" in result.output[:80] or "hist-000" in result.output
        assert "hist-001" in result.output
        assert "hist-002" in result.output
        assert "3 runs shown" in result.output

    def test_report_history_limit(self, tmp_path: Path):
        """History with --limit shows only N most recent runs."""
        store = _setup_store(tmp_path)

        for i in range(5):
            suite = _make_suite(
                run_id=f"lim-{i:03d}",
                scenario_name="limit-test",
            )
            store.save_suite_result(suite)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "--history", "--limit", "2"])

        assert result.exit_code == 0
        # Should show only last 2 runs
        assert "lim-003" in result.output[:200] or "lim-003" in result.output
        assert "lim-004" in result.output
        # First run should not appear
        assert "lim-000" not in result.output
        assert "2 runs shown" in result.output

    def test_report_history_no_runs(self, tmp_path: Path):
        """History with no runs shows message."""
        _setup_store(tmp_path)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "--history"])

        assert result.exit_code == 0
        assert "No runs found" in result.output


# ---------------------------------------------------------------------------
# Tests: Scenario filter
# ---------------------------------------------------------------------------


class TestReportScenarioFilter:
    """Test --scenario filter."""

    def test_report_scenario_filter(self, tmp_path: Path):
        """Scenario filter in history only shows matching runs."""
        store = _setup_store(tmp_path)

        suite_a = _make_suite(run_id="scn-a-001", scenario_name="alpha")
        suite_b = _make_suite(run_id="scn-b-001", scenario_name="beta")
        suite_a2 = _make_suite(run_id="scn-a-002", scenario_name="alpha")
        store.save_suite_result(suite_a)
        store.save_suite_result(suite_b)
        store.save_suite_result(suite_a2)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(
                app, ["report", "--history", "--scenario", "alpha"]
            )

        assert result.exit_code == 0
        assert "alpha" in result.output
        # beta's run_id should not appear
        assert "scn-b-00" not in result.output
        assert "2 runs shown" in result.output

    def test_report_scenario_no_match(self, tmp_path: Path):
        """Scenario filter with no matching runs shows message."""
        store = _setup_store(tmp_path)
        suite = _make_suite(run_id="only-run", scenario_name="gamma")
        store.save_suite_result(suite)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(
                app, ["report", "--history", "--scenario", "nonexistent"]
            )

        assert result.exit_code == 0
        assert "No runs found" in result.output


# ---------------------------------------------------------------------------
# Tests: Failures filter
# ---------------------------------------------------------------------------


class TestReportFailuresOnly:
    """Test --failures filter."""

    def test_report_failures_only_detail(self, tmp_path: Path):
        """Failures flag in detail mode shows only failed assertions."""
        store = _setup_store(tmp_path)

        suite = _make_suite(
            run_id="fail-detail",
            verdict=Verdict.FAIL,
            trials_passed=1,
            trials_failed=2,
            trials_total=3,
            pass_rate=0.33,
            score_avg=0.5,
            assertion_failures=[
                {
                    "assertion_type": "contains",
                    "expression": "response.body contains 'hello'",
                    "fail_count": 2,
                    "total_weight_lost": 1.0,
                    "fail_rate": 0.67,
                },
                {
                    "assertion_type": "tool_sequence",
                    "expression": "tools called in order",
                    "fail_count": 0,
                    "total_weight_lost": 0.0,
                    "fail_rate": 0.0,
                },
            ],
        )
        store.save_suite_result(suite)
        store.update_latest_symlink("fail-detail")

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "--failures"])

        assert result.exit_code == 0
        assert "contains" in result.output
        # The zero-fail-count assertion should be filtered out
        assert "tool_sequence" not in result.output

    def test_report_failures_only_history(self, tmp_path: Path):
        """Failures flag in history mode only shows non-PASS runs."""
        store = _setup_store(tmp_path)

        pass_suite = _make_suite(run_id="pass-run", verdict=Verdict.PASS)
        fail_suite = _make_suite(
            run_id="fail-run",
            verdict=Verdict.FAIL,
            trials_passed=1,
            trials_failed=2,
            trials_total=3,
            pass_rate=0.33,
            score_avg=0.5,
        )
        store.save_suite_result(pass_suite)
        store.save_suite_result(fail_suite)

        with patch("salvo.cli.report_cmd.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["report", "--history", "--failures"])

        assert result.exit_code == 0
        assert "fail-run" in result.output
        assert "pass-run" not in result.output
        assert "1 run(s) shown" in result.output
