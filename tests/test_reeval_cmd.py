"""Tests for salvo reeval CLI command."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from salvo.cli.main import app
from salvo.models.result import EvalResult

runner = CliRunner()


def _make_recorded_trace(
    *,
    run_id: str = "test-run-001",
    recording_mode: str = "full",
    scenario_name: str = "test-scenario",
    model: str = "gpt-4o",
    provider: str = "openai",
) -> dict:
    """Build a recorded trace dict for test fixtures."""
    return {
        "metadata": {
            "schema_version": 1,
            "recording_mode": recording_mode,
            "salvo_version": "0.1.0",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "source_run_id": run_id,
            "scenario_name": scenario_name,
            "scenario_file": "scenario.yaml",
            "scenario_hash": "abc123",
        },
        "trace": {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "World"},
            ],
            "tool_calls_made": [],
            "turn_count": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_seconds": 1.23,
            "final_content": "World",
            "finish_reason": "stop",
            "model": model,
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario_hash": "abc123",
            "cost_usd": 0.0042,
        },
        "scenario_snapshot": {
            "description": "Test scenario",
            "model": model,
            "prompt": "Hello",
            "adapter": "openai",
            "threshold": 0.8,
            "max_turns": 10,
            "assertions": [
                {"type": "latency_limit", "max_seconds": 5.0},
                {"type": "cost_limit", "max_usd": 0.01},
            ],
        },
    }


def _write_recorded_trace(
    tmp_path: Path,
    trace_data: dict,
    trace_id: str = "test-run-001",
) -> Path:
    """Write a .recorded.json file to the traces directory."""
    traces_dir = tmp_path / ".salvo" / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    trace_file = traces_dir / f"{trace_id}.recorded.json"
    trace_file.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")

    # Ensure runs dir exists too (for list_runs contamination test)
    runs_dir = tmp_path / ".salvo" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Ensure revals dir exists
    revals_dir = tmp_path / ".salvo" / "revals"
    revals_dir.mkdir(parents=True, exist_ok=True)

    return trace_file


def _write_scenario_file(tmp_path: Path, scenario: dict) -> Path:
    """Write a scenario YAML file."""
    import yaml

    scenario_file = tmp_path / "updated_scenario.yaml"
    scenario_file.write_text(yaml.dump(scenario), encoding="utf-8")
    return scenario_file


def _mock_eval_results_pass():
    """Return mock eval results for a passing evaluation."""
    return (
        [
            EvalResult(
                assertion_type="latency_limit",
                score=1.0,
                passed=True,
                weight=1.0,
                required=False,
                details="Latency 1.230s vs limit 5.000s",
            ),
            EvalResult(
                assertion_type="cost_limit",
                score=1.0,
                passed=True,
                weight=1.0,
                required=False,
                details="Cost $0.0042 vs limit $0.0100",
            ),
        ],
        1.0,
        True,
    )


def _mock_eval_results_fail():
    """Return mock eval results for a failing evaluation."""
    return (
        [
            EvalResult(
                assertion_type="latency_limit",
                score=0.0,
                passed=False,
                weight=1.0,
                required=False,
                details="Latency 1.230s vs limit 0.500s",
            ),
        ],
        0.0,
        False,
    )


def test_reeval_with_snapshot_assertions(tmp_path):
    """Reeval without --scenario uses frozen scenario snapshot from recording."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_pass(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 0
    assert "[RE-EVAL]" in result.output
    assert "Using original scenario snapshot" in result.output
    assert "PASS" in result.output
    assert "Re-evaluation saved:" in result.output


def test_reeval_with_updated_scenario(tmp_path):
    """Reeval with updated scenario file produces new scores."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    scenario = {
        "description": "Updated scenario",
        "model": "gpt-4o",
        "prompt": "Hello",
        "adapter": "openai",
        "threshold": 0.5,
        "max_turns": 10,
        "assertions": [
            {"type": "latency_limit", "max_seconds": 10.0},
        ],
    }
    scenario_file = _write_scenario_file(tmp_path, scenario)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_pass(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001", "--scenario", str(scenario_file)])

    assert result.exit_code == 0
    assert "[RE-EVAL]" in result.output
    assert "Using original scenario snapshot" not in result.output


def test_reeval_original_trace_id_set(tmp_path):
    """Reeval result has original_trace_id set to the input run_id."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_pass(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 0

    # Check that a reeval file was written
    revals_dir = tmp_path / ".salvo" / "revals"
    reeval_files = list(revals_dir.glob("*.json"))
    assert len(reeval_files) == 1

    reeval_data = json.loads(reeval_files[0].read_text())
    assert reeval_data["original_trace_id"] == "test-run-001"


def test_reeval_metadata_only_strict_by_default(tmp_path):
    """Reeval with metadata_only trace fails by default on content-dependent assertions."""
    trace_data = _make_recorded_trace(recording_mode="metadata_only")
    # Add a jmespath assertion to snapshot (content-dependent)
    trace_data["scenario_snapshot"]["assertions"] = [
        {"type": "jmespath", "expression": "response.content", "operator": "contains", "value": "hello"},
        {"type": "latency_limit", "max_seconds": 5.0},
    ]
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 1
    assert "require message content" in result.output
    assert "--allow-partial-reeval" in result.output


def test_reeval_metadata_only_skips_content_assertions_with_flag(tmp_path):
    """Reeval with metadata_only trace skips content-dependent assertions when --allow-partial-reeval is set."""
    trace_data = _make_recorded_trace(recording_mode="metadata_only")
    # Add a jmespath assertion to snapshot (content-dependent)
    trace_data["scenario_snapshot"]["assertions"] = [
        {"type": "jmespath", "expression": "response.content", "operator": "contains", "value": "hello"},
        {"type": "latency_limit", "max_seconds": 5.0},
    ]
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=(
                [
                    EvalResult(
                        assertion_type="latency_limit",
                        score=1.0,
                        passed=True,
                        weight=1.0,
                        required=False,
                        details="Latency OK",
                    ),
                ],
                1.0,
                True,
            ),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001", "--allow-partial-reeval"])

    assert result.exit_code == 0
    assert "1 assertion(s) skipped" in result.output


def test_reeval_nonexistent_run_id(tmp_path):
    """Reeval with nonexistent run_id shows error and exits 1."""
    # Create the .salvo dir but no traces
    (tmp_path / ".salvo" / "traces").mkdir(parents=True, exist_ok=True)

    with patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["reeval", "nonexistent-id"])

    assert result.exit_code == 1
    assert "No recorded trace found" in result.output


def test_reeval_result_saved_to_revals_dir(tmp_path):
    """Reeval result file is written to .salvo/revals/ (not .salvo/runs/)."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_pass(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 0

    # Check revals dir has the file
    revals_dir = tmp_path / ".salvo" / "revals"
    reeval_files = list(revals_dir.glob("*.json"))
    assert len(reeval_files) == 1

    # Check runs dir is NOT contaminated
    runs_dir = tmp_path / ".salvo" / "runs"
    run_files = list(runs_dir.glob("*.json"))
    assert len(run_files) == 0


def test_reeval_list_runs_not_contaminated(tmp_path):
    """list_runs should not return reeval IDs."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_pass(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 0

    # Verify list_runs returns empty (no contamination)
    from salvo.storage.json_store import RunStore

    store = RunStore(tmp_path)
    runs = store.list_runs()
    assert len(runs) == 0


def test_reeval_exit_code_pass(tmp_path):
    """Reeval exits 0 on pass."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_pass(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 0


def test_reeval_exit_code_fail(tmp_path):
    """Reeval exits 1 on fail."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with (
        patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path),
        patch(
            "salvo.evaluation.scorer.evaluate_trace_async",
            new_callable=AsyncMock,
            return_value=_mock_eval_results_fail(),
        ),
    ):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 1
    assert "FAIL" in result.output


def test_reeval_metadata_only_all_content_assertions(tmp_path):
    """Reeval with metadata_only and ALL content-dependent assertions errors out."""
    trace_data = _make_recorded_trace(recording_mode="metadata_only")
    trace_data["scenario_snapshot"]["assertions"] = [
        {"type": "jmespath", "expression": "response.content", "operator": "contains", "value": "hello"},
    ]
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.reeval_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["reeval", "test-run-001"])

    assert result.exit_code == 1
    assert "Re-evaluation not possible" in result.output
