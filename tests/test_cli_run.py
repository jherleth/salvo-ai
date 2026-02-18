"""Tests for the salvo run CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)
from salvo.cli.main import app

runner = CliRunner()


class CLIMockAdapter(BaseAdapter):
    """Mock adapter for CLI testing that returns configurable responses."""

    def __init__(self, responses: list[AdapterTurnResult] | None = None) -> None:
        self._responses = responses or [
            AdapterTurnResult(
                content="Mock response",
                tool_calls=[],
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
                raw_response={},
                finish_reason="stop",
            ),
        ]
        self._call_count = 0

    async def send_turn(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        config: AdapterConfig | None = None,
    ) -> AdapterTurnResult:
        if self._call_count >= len(self._responses):
            raise RuntimeError("CLIMockAdapter exhausted responses")
        result = self._responses[self._call_count]
        self._call_count += 1
        return result

    def provider_name(self) -> str:
        return "CLIMockAdapter"


def _write_scenario(tmp_path: Path, content: str | None = None) -> Path:
    """Write a minimal valid scenario YAML to tmp_path and return its path."""
    if content is None:
        content = (
            "model: gpt-4o\n"
            "prompt: Hello world\n"
            "description: Test scenario\n"
        )
    scenario_file = tmp_path / "test_scenario.yaml"
    scenario_file.write_text(content, encoding="utf-8")
    return scenario_file


def test_run_command_with_mock_adapter(tmp_path: Path):
    """Run command with mock adapter succeeds with summary output."""
    scenario_file = _write_scenario(tmp_path)

    mock_adapter = CLIMockAdapter()
    with patch("salvo.cli.run_cmd.get_adapter", return_value=mock_adapter):
        result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert "gpt-4o" in result.output
    assert "1" in result.output  # turn count
    assert "Run saved:" in result.output


def test_run_command_invalid_scenario(tmp_path: Path):
    """Invalid scenario YAML produces error and exit code 1."""
    scenario_file = _write_scenario(
        tmp_path, content="not_a_field: true\nmodel: gpt-4o\n"
    )

    result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 1
    # Should mention validation error
    assert "validation" in result.output.lower() or "error" in result.output.lower()


def test_run_command_missing_sdk(tmp_path: Path):
    """Missing SDK raises ImportError with install hint."""
    scenario_file = _write_scenario(tmp_path)

    with patch(
        "salvo.cli.run_cmd.get_adapter",
        side_effect=ImportError(
            "Adapter 'openai' requires the openai package. Install it: pip install salvo-ai[openai]"
        ),
    ):
        result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 1
    assert "openai" in result.output.lower() or "install" in result.output.lower()


def test_run_command_tool_mock_not_found(tmp_path: Path):
    """Model calling unknown tool produces error and exit code 1."""
    content = (
        "model: gpt-4o\n"
        "prompt: Use the tool\n"
        "tools:\n"
        "  - name: search\n"
        "    description: Search\n"
        "    mock_response: data\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    # Adapter calls a tool that has no mock
    mock_adapter = CLIMockAdapter(responses=[
        AdapterTurnResult(
            content=None,
            tool_calls=[ToolCallResult(id="tc1", name="nonexistent", arguments={})],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_response={},
            finish_reason="tool_calls",
        ),
    ])

    with patch("salvo.cli.run_cmd.get_adapter", return_value=mock_adapter):
        result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 1
    assert "mock" in result.output.lower() or "nonexistent" in result.output.lower()


def test_run_command_saves_to_store(tmp_path: Path):
    """Successful run saves RunResult to .salvo/runs/."""
    scenario_file = _write_scenario(tmp_path)

    mock_adapter = CLIMockAdapter()
    with (
        patch("salvo.cli.run_cmd.get_adapter", return_value=mock_adapter),
        patch("salvo.cli.run_cmd._find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 0, f"Output: {result.output}"

    # Check .salvo/runs/ has a JSON file
    runs_dir = tmp_path / ".salvo" / "runs"
    assert runs_dir.exists()
    run_files = list(runs_dir.glob("*.json"))
    assert len(run_files) == 1

    # Verify the file is valid JSON with expected fields
    data = json.loads(run_files[0].read_text())
    assert "run_id" in data
    assert "metadata" in data
    assert data["metadata"]["model"] == "gpt-4o"


def test_cli_run_extras_validated(tmp_path: Path):
    """Scenario with blocked extras key causes exit code 1."""
    content = (
        "model: gpt-4o\n"
        "prompt: Hello\n"
        "extras:\n"
        "  api_key: secret123\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    mock_adapter = CLIMockAdapter()
    with patch("salvo.cli.run_cmd.get_adapter", return_value=mock_adapter):
        result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 1
    assert "blocked" in result.output.lower() or "secret" in result.output.lower()


def test_run_command_saves_trace(tmp_path: Path):
    """Successful run saves redacted trace to .salvo/traces/{run_id}.json."""
    scenario_file = _write_scenario(tmp_path)

    mock_adapter = CLIMockAdapter()
    with (
        patch("salvo.cli.run_cmd.get_adapter", return_value=mock_adapter),
        patch("salvo.cli.run_cmd._find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file)])

    assert result.exit_code == 0, f"Output: {result.output}"

    # Check .salvo/traces/ has a JSON file
    traces_dir = tmp_path / ".salvo" / "traces"
    assert traces_dir.exists()
    trace_files = list(traces_dir.glob("*.json"))
    assert len(trace_files) == 1

    # Verify the trace is valid JSON with expected fields
    data = json.loads(trace_files[0].read_text())
    assert "messages" in data
    assert "turn_count" in data
    assert "model" in data
    assert data["model"] == "gpt-4o"
    assert data["turn_count"] == 1
