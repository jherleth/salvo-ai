"""Tests for salvo.cli.run_cmd N-trial integration and json_store suite methods."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salvo.models.trial import (
    TrialResult,
    TrialStatus,
    TrialSuiteResult,
    Verdict,
)
from salvo.storage.json_store import RunStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suite(
    run_id: str = "test-run-001",
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
    early_stopped: bool = False,
    n_requested: int = 3,
) -> TrialSuiteResult:
    """Create a minimal TrialSuiteResult for testing."""
    trials = [
        TrialResult(
            trial_number=i + 1,
            status=TrialStatus.passed,
            score=1.0,
            passed=True,
            latency_seconds=1.5,
            cost_usd=0.01,
        )
        for i in range(trials_passed)
    ]
    for i in range(trials_failed):
        trials.append(
            TrialResult(
                trial_number=trials_passed + i + 1,
                status=TrialStatus.failed,
                score=0.0,
                passed=False,
                latency_seconds=1.5,
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
        scenario_name="test-scenario",
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
        early_stopped=early_stopped,
        n_requested=n_requested,
    )


# ---------------------------------------------------------------------------
# Tests: RunStore suite methods
# ---------------------------------------------------------------------------


class TestRunStoreSuiteResult:
    """Test save/load/latest for TrialSuiteResult."""

    def test_save_and_load_suite_result(self, tmp_path: Path):
        """Suite result round-trips through save/load."""
        store = RunStore(tmp_path)
        suite = _make_suite(run_id="suite-001")

        returned_id = store.save_suite_result(suite)

        assert returned_id == "suite-001"
        assert (tmp_path / ".salvo" / "runs" / "suite-001.json").exists()

        loaded = store.load_suite_result("suite-001")
        assert loaded.run_id == "suite-001"
        assert loaded.verdict == Verdict.PASS
        assert loaded.trials_total == 3
        assert len(loaded.trials) == 3

    def test_suite_result_json_valid(self, tmp_path: Path):
        """Saved suite result is valid JSON."""
        store = RunStore(tmp_path)
        suite = _make_suite(run_id="suite-002")
        store.save_suite_result(suite)

        path = tmp_path / ".salvo" / "runs" / "suite-002.json"
        data = json.loads(path.read_text())
        assert data["run_id"] == "suite-002"
        assert data["verdict"] == "PASS"

    def test_load_nonexistent_suite_raises(self, tmp_path: Path):
        """Loading nonexistent suite raises FileNotFoundError."""
        store = RunStore(tmp_path)
        store.ensure_dirs()
        with pytest.raises(FileNotFoundError):
            store.load_suite_result("nonexistent")

    def test_suite_updates_index(self, tmp_path: Path):
        """save_suite_result updates the index file."""
        store = RunStore(tmp_path)
        suite = _make_suite(run_id="suite-003")
        store.save_suite_result(suite)

        index_path = tmp_path / ".salvo" / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text())
        assert "test-scenario" in index
        assert "suite-003" in index["test-scenario"]


class TestRunStoreLatestSymlink:
    """Test latest symlink creation and reading."""

    def test_create_latest_symlink(self, tmp_path: Path):
        """update_latest_symlink creates a symlink."""
        store = RunStore(tmp_path)
        suite = _make_suite(run_id="latest-001")
        store.save_suite_result(suite)
        store.update_latest_symlink("latest-001")

        link_path = tmp_path / ".salvo" / "runs" / "latest"
        assert link_path.is_symlink() or link_path.exists()

    def test_load_latest_suite(self, tmp_path: Path):
        """load_latest_suite returns the most recent suite."""
        store = RunStore(tmp_path)
        suite = _make_suite(run_id="latest-002")
        store.save_suite_result(suite)
        store.update_latest_symlink("latest-002")

        loaded = store.load_latest_suite()
        assert loaded is not None
        assert loaded.run_id == "latest-002"

    def test_load_latest_suite_none_when_missing(self, tmp_path: Path):
        """load_latest_suite returns None when no latest exists."""
        store = RunStore(tmp_path)
        store.ensure_dirs()
        result = store.load_latest_suite()
        assert result is None

    def test_update_latest_overwrites(self, tmp_path: Path):
        """Updating latest symlink replaces the old one."""
        store = RunStore(tmp_path)

        suite1 = _make_suite(run_id="run-aaa")
        store.save_suite_result(suite1)
        store.update_latest_symlink("run-aaa")

        suite2 = _make_suite(run_id="run-bbb")
        store.save_suite_result(suite2)
        store.update_latest_symlink("run-bbb")

        loaded = store.load_latest_suite()
        assert loaded is not None
        assert loaded.run_id == "run-bbb"


# ---------------------------------------------------------------------------
# Tests: Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    """Test that EXIT_CODES map correctly to verdicts."""

    def test_exit_code_mapping(self):
        """Verify the static exit code mapping."""
        from salvo.cli.run_cmd import EXIT_CODES

        assert EXIT_CODES["PASS"] == 0
        assert EXIT_CODES["FAIL"] == 1
        assert EXIT_CODES["HARD FAIL"] == 2
        assert EXIT_CODES["PARTIAL"] == 1
        assert EXIT_CODES["INFRA_ERROR"] == 3


# ---------------------------------------------------------------------------
# Tests: JSON output via run command
# ---------------------------------------------------------------------------


class TestRunCmdJsonOutput:
    """Test --json flag produces valid JSON on stdout."""

    def test_json_flag_output(self, tmp_path: Path, capsys):
        """--json flag writes valid JSON to stdout."""
        from salvo.cli.output import output_json

        suite = _make_suite()
        output_json(suite)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["verdict"] == "PASS"
        assert "bold" not in captured.out
        assert "[/" not in captured.out


# ---------------------------------------------------------------------------
# Tests: run_cmd imports
# ---------------------------------------------------------------------------


class TestRunCmdImports:
    """Test that refactored run_cmd is importable and has correct signature."""

    def test_run_importable(self):
        """run function importable from salvo.cli.run_cmd."""
        from salvo.cli.run_cmd import run
        assert callable(run)

    def test_run_store_importable(self):
        """RunStore importable from salvo.storage.json_store."""
        from salvo.storage.json_store import RunStore
        assert RunStore is not None

    def test_exit_codes_importable(self):
        """EXIT_CODES dict importable from run_cmd."""
        from salvo.cli.run_cmd import EXIT_CODES
        assert isinstance(EXIT_CODES, dict)
        assert len(EXIT_CODES) == 5


# ---------------------------------------------------------------------------
# Tests: Allow-infra behavior
# ---------------------------------------------------------------------------


class TestAllowInfra:
    """Test --allow-infra changes exit code behavior."""

    def test_allow_infra_remaps_verdict(self):
        """With allow_infra, INFRA_ERROR verdict can become PASS/FAIL."""
        from salvo.evaluation.aggregation import compute_aggregate_metrics, determine_verdict

        # Mixed: 2 passed, 1 infra error
        trials = [
            TrialResult(
                trial_number=1, status=TrialStatus.passed, score=1.0,
                passed=True, latency_seconds=1.0,
            ),
            TrialResult(
                trial_number=2, status=TrialStatus.passed, score=1.0,
                passed=True, latency_seconds=1.0,
            ),
            TrialResult(
                trial_number=3, status=TrialStatus.infra_error, score=0.0,
                passed=False, latency_seconds=0.5, error_message="timeout",
            ),
        ]

        # Without allow_infra -> INFRA_ERROR
        verdict_no_allow = determine_verdict(trials, 1.0, 0.8, allow_infra=False)
        assert verdict_no_allow == Verdict.INFRA_ERROR

        # With allow_infra -> look at scored trials only -> PASS
        scored = [t for t in trials if t.status != TrialStatus.infra_error]
        metrics = compute_aggregate_metrics(scored, 0.8)
        verdict_allow = determine_verdict(scored, metrics["score_avg"], 0.8, allow_infra=True)
        assert verdict_allow == Verdict.PASS


# ---------------------------------------------------------------------------
# Tests: Suite persistence end-to-end
# ---------------------------------------------------------------------------


class TestSuitePersistenceE2E:
    """Test complete save + load + latest workflow."""

    def test_full_persistence_cycle(self, tmp_path: Path):
        """Save suite, update latest, load latest, verify data."""
        store = RunStore(tmp_path)

        suite = _make_suite(
            run_id="e2e-run-001",
            verdict=Verdict.FAIL,
            trials_total=5,
            trials_passed=2,
            trials_failed=3,
            pass_rate=0.4,
            score_avg=0.6,
            score_min=0.0,
            score_p50=0.5,
            score_p95=0.9,
        )

        store.save_suite_result(suite)
        store.update_latest_symlink(suite.run_id)

        # Verify file exists
        run_file = tmp_path / ".salvo" / "runs" / "e2e-run-001.json"
        assert run_file.exists()

        # Load via latest
        loaded = store.load_latest_suite()
        assert loaded is not None
        assert loaded.run_id == "e2e-run-001"
        assert loaded.verdict == Verdict.FAIL
        assert loaded.trials_total == 5
        assert loaded.trials_passed == 2
        assert loaded.score_avg == 0.6

        # Load directly
        direct = store.load_suite_result("e2e-run-001")
        assert direct.run_id == loaded.run_id

    def test_multiple_suites_latest_points_to_last(self, tmp_path: Path):
        """Multiple saves, latest always points to the most recent."""
        store = RunStore(tmp_path)

        for i in range(3):
            suite = _make_suite(run_id=f"multi-{i:03d}")
            store.save_suite_result(suite)
            store.update_latest_symlink(suite.run_id)

        loaded = store.load_latest_suite()
        assert loaded is not None
        assert loaded.run_id == "multi-002"
