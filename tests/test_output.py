"""Tests for salvo.cli.output - Rich verdict rendering layer."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from rich.console import Console

from salvo.cli.output import (
    create_trial_progress,
    output_json,
    render_details,
    render_headline,
)
from salvo.models.trial import (
    TrialResult,
    TrialStatus,
    TrialSuiteResult,
    Verdict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suite(
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
    cost_total: float | None = None,
    cost_avg_per_trial: float | None = None,
    latency_p50: float | None = 1.5,
    latency_p95: float | None = 2.0,
    total_retries: int = 0,
    trials_with_retries: int = 0,
    early_stopped: bool = False,
    early_stop_reason: str | None = None,
    n_requested: int = 3,
    assertion_failures: list[dict] | None = None,
    trials: list[TrialResult] | None = None,
) -> TrialSuiteResult:
    """Create a TrialSuiteResult with sensible defaults for testing."""
    if trials is None:
        trials = [
            TrialResult(
                trial_number=i + 1,
                status=TrialStatus.passed,
                score=score_avg,
                passed=True,
                latency_seconds=1.5,
                cost_usd=0.01,
            )
            for i in range(trials_passed)
        ]
        # Add failed trials
        for i in range(trials_failed):
            trials.append(
                TrialResult(
                    trial_number=trials_passed + i + 1,
                    status=TrialStatus.failed,
                    score=0.0,
                    passed=False,
                    latency_seconds=1.5,
                    cost_usd=0.01,
                )
            )
        # Add hard fail trials
        for i in range(trials_hard_fail):
            trials.append(
                TrialResult(
                    trial_number=trials_passed + trials_failed + i + 1,
                    status=TrialStatus.hard_fail,
                    score=0.0,
                    passed=False,
                    latency_seconds=1.5,
                    cost_usd=0.01,
                )
            )
        # Add infra error trials
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
        run_id="test-run-001",
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
        cost_total=cost_total,
        cost_avg_per_trial=cost_avg_per_trial,
        latency_p50=latency_p50,
        latency_p95=latency_p95,
        total_retries=total_retries,
        trials_with_retries=trials_with_retries,
        early_stopped=early_stopped,
        early_stop_reason=early_stop_reason,
        n_requested=n_requested,
        assertion_failures=assertion_failures or [],
    )


def _capture_console() -> tuple[Console, StringIO]:
    """Create a Console that captures output to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    return console, buf


# ---------------------------------------------------------------------------
# Tests: render_headline
# ---------------------------------------------------------------------------


class TestRenderHeadline:
    """Test headline table rendering for each verdict type."""

    def test_pass_verdict(self):
        """PASS verdict shows check mark and green styling reference."""
        suite = _make_suite(verdict=Verdict.PASS)
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "\u2713 PASS" in output
        assert "3/3 passed" in output

    def test_fail_verdict(self):
        """FAIL verdict shows X mark."""
        suite = _make_suite(
            verdict=Verdict.FAIL,
            trials_passed=0,
            trials_failed=3,
            pass_rate=0.0,
            score_avg=0.0,
            score_min=0.0,
            score_p50=0.0,
            score_p95=0.0,
        )
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "\u2717 FAIL" in output
        assert "0/3 passed" in output

    def test_hard_fail_verdict(self):
        """HARD FAIL verdict shows exclamation mark."""
        suite = _make_suite(
            verdict=Verdict.HARD_FAIL,
            trials_passed=0,
            trials_failed=0,
            trials_hard_fail=3,
            pass_rate=0.0,
            score_avg=0.0,
            score_min=0.0,
            score_p50=0.0,
            score_p95=0.0,
        )
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "! HARD FAIL" in output
        assert "hard fail" in output

    def test_partial_verdict(self):
        """PARTIAL verdict shows tilde."""
        suite = _make_suite(
            verdict=Verdict.PARTIAL,
            trials_passed=1,
            trials_failed=2,
            pass_rate=0.33,
            score_avg=0.5,
            score_min=0.0,
            score_p50=0.5,
            score_p95=0.8,
        )
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "~ PARTIAL" in output
        assert "1/3 passed" in output

    def test_infra_error_verdict(self):
        """INFRA_ERROR verdict shows exclamation and infra count."""
        suite = _make_suite(
            verdict=Verdict.INFRA_ERROR,
            trials_passed=0,
            trials_failed=0,
            trials_infra_error=3,
            pass_rate=0.0,
            score_avg=0.0,
            score_min=0.0,
            score_p50=0.0,
            score_p95=0.0,
            latency_p50=0.5,
            latency_p95=0.5,
        )
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "! INFRA ERROR" in output
        assert "3 trial(s) (excluded from score)" in output

    def test_score_row_values(self):
        """Score row shows avg, min, p50, p95, and threshold."""
        suite = _make_suite(
            score_avg=0.85,
            score_min=0.60,
            score_p50=0.90,
            score_p95=0.95,
            threshold=0.80,
        )
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "avg=0.85" in output
        assert "min=0.60" in output
        assert "p50=0.90" in output
        assert "p95=0.95" in output
        assert "threshold=0.80" in output

    def test_latency_row_shown(self):
        """Latency row appears when p50 and p95 are set."""
        suite = _make_suite(latency_p50=1.23, latency_p95=4.56)
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "p50=1.23s" in output
        assert "p95=4.56s" in output

    def test_cost_row_shown(self):
        """Cost row appears when cost_total and cost_avg are set."""
        suite = _make_suite(cost_total=0.1234, cost_avg_per_trial=0.0411)
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "total=$0.1234" in output
        assert "avg=$0.0411/trial" in output

    def test_no_failures_row_when_none(self):
        """Failures row is omitted when no hard fail or soft fail."""
        suite = _make_suite(trials_hard_fail=0, trials_failed=0)
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "hard fail" not in output.lower().replace("! hard fail", "")

    def test_retries_row_shown(self):
        """Retries row appears when total_retries > 0."""
        suite = _make_suite(total_retries=5, trials_with_retries=2)
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "5 retries across 2 trials" in output

    def test_early_stop_row_shown(self):
        """Early stop status row appears when early_stopped is True."""
        suite = _make_suite(
            early_stopped=True,
            trials_total=2,
            n_requested=10,
            verdict=Verdict.FAIL,
            trials_passed=0,
            trials_failed=2,
            pass_rate=0.0,
            score_avg=0.0,
            score_min=0.0,
            score_p50=0.0,
            score_p95=0.0,
        )
        console, buf = _capture_console()
        render_headline(suite, console)
        output = buf.getvalue()
        assert "early stop after 2/10 trials" in output


# ---------------------------------------------------------------------------
# Tests: render_details
# ---------------------------------------------------------------------------


class TestRenderDetails:
    """Test detail section rendering."""

    def test_top_offenders_shown(self):
        """Top offenders section displays failure info."""
        suite = _make_suite(
            verdict=Verdict.FAIL,
            assertion_failures=[
                {
                    "assertion_type": "jmespath",
                    "expression": "response.content contains hello",
                    "fail_count": 2,
                    "fail_rate": 0.67,
                    "total_weight_lost": 1.5,
                    "sample_details": ["Expected hello, got goodbye"],
                },
            ],
        )
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        assert "Top Offenders" in output
        assert "jmespath" in output
        assert "failed 2/3" in output

    def test_top_offenders_limited_to_5(self):
        """Only top 5 offenders shown even if more exist."""
        failures = [
            {
                "assertion_type": f"type_{i}",
                "expression": f"expr_{i}",
                "fail_count": 1,
                "fail_rate": 0.33,
                "total_weight_lost": 0.5,
                "sample_details": [],
            }
            for i in range(8)
        ]
        suite = _make_suite(assertion_failures=failures)
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        assert "type_4" in output
        assert "type_5" not in output

    def test_score_breakdown_shown(self):
        """Score breakdown lists per-trial scores."""
        trials = [
            TrialResult(
                trial_number=1, status=TrialStatus.passed, score=1.0,
                passed=True, latency_seconds=1.0,
            ),
            TrialResult(
                trial_number=2, status=TrialStatus.failed, score=0.5,
                passed=False, latency_seconds=2.0,
            ),
        ]
        suite = _make_suite(
            trials=trials,
            trials_total=2,
            trials_passed=1,
            trials_failed=1,
        )
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        assert "Scores:" in output
        assert "1.0" in output
        assert "0.5" in output

    def test_latency_distribution_shown(self):
        """Latency distribution shows min, p50, p95, max."""
        suite = _make_suite(latency_p50=1.5, latency_p95=2.0)
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        assert "Latency:" in output
        assert "min=" in output
        assert "max=" in output

    def test_cost_breakdown_shown(self):
        """Cost breakdown shows total, min, max, avg."""
        suite = _make_suite(cost_total=0.03, cost_avg_per_trial=0.01)
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        assert "Cost:" in output
        assert "total=$0.0300" in output

    def test_sample_failures_shown(self):
        """Sample failures section displays truncated detail strings."""
        suite = _make_suite(
            assertion_failures=[
                {
                    "assertion_type": "jmespath",
                    "expression": "response.content",
                    "fail_count": 1,
                    "fail_rate": 0.33,
                    "total_weight_lost": 1.0,
                    "sample_details": [
                        "Expected 'hello' but got 'goodbye'",
                        "Another failure detail",
                    ],
                },
            ],
        )
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        assert "Sample Failures" in output
        assert "Expected 'hello' but got 'goodbye'" in output

    def test_sample_failures_truncated_at_200(self):
        """Long sample details are truncated to 200 chars."""
        long_detail = "x" * 300
        suite = _make_suite(
            assertion_failures=[
                {
                    "assertion_type": "jmespath",
                    "expression": "expr",
                    "fail_count": 1,
                    "fail_rate": 0.33,
                    "total_weight_lost": 1.0,
                    "sample_details": [long_detail],
                },
            ],
        )
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        # Should have ellipsis after truncation, not the full 300 chars
        assert "..." in output

    def test_infra_error_trials_excluded_from_scores(self):
        """Infra error trials are not included in score breakdown."""
        trials = [
            TrialResult(
                trial_number=1, status=TrialStatus.passed, score=1.0,
                passed=True, latency_seconds=1.0,
            ),
            TrialResult(
                trial_number=2, status=TrialStatus.infra_error, score=0.0,
                passed=False, latency_seconds=0.5, error_message="boom",
            ),
        ]
        suite = _make_suite(
            trials=trials,
            trials_total=2,
            trials_passed=1,
            trials_infra_error=1,
        )
        console, buf = _capture_console()
        render_details(suite, console)
        output = buf.getvalue()
        # Score breakdown should only list 1 trial score (the passed one)
        scores_line = [l for l in output.split("\n") if "Scores:" in l]
        assert len(scores_line) == 1
        assert "1.0" in scores_line[0]


# ---------------------------------------------------------------------------
# Tests: output_json
# ---------------------------------------------------------------------------


class TestOutputJson:
    """Test JSON output mode."""

    def test_valid_json_output(self, capsys):
        """output_json writes valid JSON to stdout."""
        suite = _make_suite()
        output_json(suite)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["run_id"] == "test-run-001"
        assert data["verdict"] == "PASS"
        assert data["score_avg"] == 1.0

    def test_no_rich_markup_in_json(self, capsys):
        """JSON output contains no Rich markup tags."""
        suite = _make_suite(verdict=Verdict.FAIL)
        output_json(suite)
        captured = capsys.readouterr()
        assert "[bold" not in captured.out
        assert "[/" not in captured.out

    def test_json_includes_all_trials(self, capsys):
        """JSON output includes all trial results."""
        suite = _make_suite(trials_total=3, trials_passed=3)
        output_json(suite)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data["trials"]) == 3


# ---------------------------------------------------------------------------
# Tests: create_trial_progress
# ---------------------------------------------------------------------------


class TestCreateTrialProgress:
    """Test progress bar creation."""

    def test_returns_progress_for_terminal(self):
        """Returns Progress instance when console is a terminal."""
        console = Console(force_terminal=True)
        progress = create_trial_progress(console)
        assert progress is not None

    def test_returns_none_for_non_terminal(self):
        """Returns None when console is not a terminal."""
        console = Console(file=StringIO(), force_terminal=False)
        progress = create_trial_progress(console)
        assert progress is None


# ---------------------------------------------------------------------------
# Tests: Non-TTY mode
# ---------------------------------------------------------------------------


class TestNonTTYMode:
    """Test that non-TTY/CI mode works without ANSI garbage."""

    def test_headline_no_ansi_in_non_terminal(self):
        """Headline renders without ANSI escape codes in non-TTY mode."""
        suite = _make_suite()
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, no_color=True, width=120)
        render_headline(suite, console)
        output = buf.getvalue()
        # Should have the verdict symbol but no ANSI escapes
        assert "\u2713 PASS" in output
        assert "\x1b[" not in output

    def test_details_no_ansi_in_non_terminal(self):
        """Details render without ANSI escape codes in non-TTY mode."""
        suite = _make_suite(
            assertion_failures=[
                {
                    "assertion_type": "jmespath",
                    "expression": "response.content",
                    "fail_count": 1,
                    "fail_rate": 0.33,
                    "total_weight_lost": 1.0,
                    "sample_details": ["test detail"],
                },
            ],
        )
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, no_color=True, width=120)
        render_details(suite, console)
        output = buf.getvalue()
        assert "Top Offenders" in output
        assert "\x1b[" not in output
