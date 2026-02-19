"""Tests for salvo replay CLI command."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from salvo.cli.main import app

runner = CliRunner()


def _make_recorded_trace(
    *,
    run_id: str = "test-run-001",
    recording_mode: str = "full",
    scenario_name: str = "test-scenario",
    model: str = "gpt-4o",
    provider: str = "openai",
    final_content: str = "Hello, world!",
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
                {"role": "assistant", "content": final_content},
                {"role": "user", "content": "Follow up"},
                {"role": "assistant", "content": "Response"},
            ],
            "tool_calls_made": [],
            "turn_count": 2,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_seconds": 1.23,
            "final_content": final_content
            if recording_mode == "full"
            else "[CONTENT_EXCLUDED]",
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
        },
    }


def _write_recorded_trace(
    tmp_path: Path,
    trace_data: dict,
    trace_id: str = "trace-001",
) -> Path:
    """Write a .recorded.json file and set up latest-recorded symlink."""
    traces_dir = tmp_path / ".salvo" / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    trace_file = traces_dir / f"{trace_id}.recorded.json"
    trace_file.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")

    # Create latest-recorded fallback
    fallback = traces_dir / ".latest-recorded"
    fallback.write_text(trace_id, encoding="utf-8")

    return trace_file


def test_replay_no_recorded_traces(tmp_path):
    """Replay with no recorded traces shows helpful message and exits 0."""
    salvo_dir = tmp_path / ".salvo" / "traces"
    salvo_dir.mkdir(parents=True, exist_ok=True)

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay"])

    assert result.exit_code == 0
    assert "No recorded traces found" in result.output
    assert "salvo run --record" in result.output


def test_replay_latest_trace(tmp_path):
    """Replay with no argument loads latest recorded trace."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay"])

    assert result.exit_code == 0
    assert "[REPLAY]" in result.output
    assert "test-scenario" in result.output
    assert "gpt-4o" in result.output
    assert "openai" in result.output
    assert "(recorded)" in result.output
    assert "Hello, world!" in result.output
    assert "Schema version: 1" in result.output


def test_replay_specific_run_id(tmp_path):
    """Replay of a specific run_id loads the correct trace."""
    trace_data = _make_recorded_trace(run_id="specific-run")
    _write_recorded_trace(tmp_path, trace_data, trace_id="specific-run")

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay", "specific-run"])

    assert result.exit_code == 0
    assert "[REPLAY]" in result.output
    assert "specific-run" in result.output


def test_replay_metadata_only_warning(tmp_path):
    """Metadata_only trace shows content excluded warning."""
    trace_data = _make_recorded_trace(recording_mode="metadata_only")
    # For metadata_only, content is excluded
    trace_data["trace"]["final_content"] = "[CONTENT_EXCLUDED]"
    for msg in trace_data["trace"]["messages"]:
        msg["content"] = "[CONTENT_EXCLUDED]"
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay"])

    assert result.exit_code == 0
    assert "Content excluded" in result.output or "metadata_only" in result.output
    assert "[CONTENT_EXCLUDED]" in result.output


def test_replay_no_api_calls():
    """Replay command does not import any adapter modules."""
    import salvo.cli.replay_cmd as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    # Should not import adapters
    assert "from salvo.adapters" not in source
    assert "get_adapter" not in source


def test_replay_message_summary(tmp_path):
    """Replay shows message count by role."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay"])

    assert result.exit_code == 0
    assert "Messages:" in result.output
    assert "user" in result.output
    assert "assistant" in result.output


def test_replay_cost_display(tmp_path):
    """Replay shows cost with (recorded) suffix."""
    trace_data = _make_recorded_trace()
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay"])

    assert result.exit_code == 0
    assert "$0.0042" in result.output
    assert "(recorded)" in result.output


def test_replay_cost_none(tmp_path):
    """Replay shows '-' when cost_usd is None."""
    trace_data = _make_recorded_trace()
    trace_data["trace"]["cost_usd"] = None
    _write_recorded_trace(tmp_path, trace_data)

    with patch("salvo.cli.replay_cmd.find_project_root", return_value=tmp_path):
        result = runner.invoke(app, ["replay"])

    assert result.exit_code == 0
    # Should show "-" for missing cost
    assert "-" in result.output
