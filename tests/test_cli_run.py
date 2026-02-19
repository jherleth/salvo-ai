"""Tests for the salvo run CLI command.

Updated for N-trial architecture: run_cmd now uses TrialRunner with N=3 default.
The adapter_factory creates a fresh adapter per trial, so get_adapter must return
a new instance each call (side_effect, not return_value).
"""

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
        self._responses = list(responses) if responses else [
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


def _mock_adapter_factory(
    responses: list[AdapterTurnResult] | None = None,
) -> MagicMock:
    """Create a side_effect function that returns a fresh CLIMockAdapter per call.

    With N-trial architecture, get_adapter is called once for validation
    and then once per trial via adapter_factory. Each call must return
    a fresh adapter with its own response list.
    """
    def _factory(adapter_name: str | None = None) -> CLIMockAdapter:
        return CLIMockAdapter(responses=responses)
    return _factory


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
    """Run command with mock adapter succeeds with verdict output (no assertions = vacuous pass)."""
    scenario_file = _write_scenario(tmp_path)

    with patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert "Run saved:" in result.output
    assert "PASS" in result.output


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
    """Model calling unknown tool produces infra error (ToolMockNotFoundError is caught by retry/runner)."""
    content = (
        "model: gpt-4o\n"
        "prompt: Use the tool\n"
        "tools:\n"
        "  - name: search\n"
        "    description: Search\n"
        "    mock_response: data\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    # Adapter calls a tool that has no mock -- with N-trial architecture,
    # ToolMockNotFoundError is caught by the runner and becomes an infra error.
    bad_responses = [
        AdapterTurnResult(
            content=None,
            tool_calls=[ToolCallResult(id="tc1", name="nonexistent", arguments={})],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_response={},
            finish_reason="tool_calls",
        ),
    ]

    with patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory(bad_responses)):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    # ToolMockNotFoundError caught by TrialRunner -> INFRA_ERROR -> exit 3
    assert result.exit_code == 3
    assert "INFRA ERROR" in result.output


def test_run_command_saves_to_store(tmp_path: Path):
    """Successful run saves TrialSuiteResult to .salvo/runs/."""
    scenario_file = _write_scenario(tmp_path)

    with (
        patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()),
        patch("salvo.cli.run_cmd.find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 0, f"Output: {result.output}"

    # Check .salvo/runs/ has a JSON file (exclude 'latest' symlink)
    runs_dir = tmp_path / ".salvo" / "runs"
    assert runs_dir.exists()
    run_files = [f for f in runs_dir.glob("*.json") if f.name != "latest"]
    assert len(run_files) == 1

    # Verify the file is valid JSON with TrialSuiteResult fields
    data = json.loads(run_files[0].read_text())
    assert "run_id" in data
    assert "model" in data
    assert data["model"] == "gpt-4o"
    assert "verdict" in data


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


def test_run_command_saves_suite_with_latest(tmp_path: Path):
    """Successful run saves suite result and creates latest symlink."""
    scenario_file = _write_scenario(tmp_path)

    with (
        patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()),
        patch("salvo.cli.run_cmd.find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 0, f"Output: {result.output}"

    # Check latest symlink exists
    runs_dir = tmp_path / ".salvo" / "runs"
    latest = runs_dir / "latest"
    assert latest.is_symlink() or latest.exists() or (runs_dir / ".latest").exists()


def test_run_command_assertions_pass(tmp_path: Path):
    """Scenario with passing assertions shows PASS verdict."""
    content = (
        "model: gpt-4o\n"
        "prompt: Say hello\n"
        "description: Test passing assertions\n"
        "assertions:\n"
        "  - path: response.content\n"
        "    contains: Mock response\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    with (
        patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()),
        patch("salvo.cli.run_cmd.find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert "PASS" in result.output
    assert "avg=1.00" in result.output


def test_run_command_assertions_fail(tmp_path: Path):
    """Scenario with failing assertions shows FAIL verdict and exit code 1."""
    content = (
        "model: gpt-4o\n"
        "prompt: Say hello\n"
        "description: Test failing assertions\n"
        "assertions:\n"
        "  - path: response.content\n"
        "    contains: NONEXISTENT_STRING\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    with (
        patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()),
        patch("salvo.cli.run_cmd.find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "avg=0.00" in result.output


def test_run_command_required_assertion_hard_fail(tmp_path: Path):
    """Required assertion failure shows HARD FAIL verdict and exit code 2."""
    content = (
        "model: gpt-4o\n"
        "prompt: Say hello\n"
        "description: Test hard fail\n"
        "assertions:\n"
        "  - path: response.content\n"
        "    contains: NONEXISTENT\n"
        "    required: true\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    with (
        patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()),
        patch("salvo.cli.run_cmd.find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 2  # HARD FAIL exits with code 2
    assert "HARD FAIL" in result.output


def test_run_command_persists_real_score(tmp_path: Path):
    """TrialSuiteResult stored in .salvo/runs/ contains real verdict and score values."""
    content = (
        "model: gpt-4o\n"
        "prompt: Say hello\n"
        "description: Test persistence\n"
        "assertions:\n"
        "  - path: response.content\n"
        "    contains: Mock response\n"
    )
    scenario_file = _write_scenario(tmp_path, content=content)

    with (
        patch("salvo.cli.run_cmd.get_adapter", side_effect=_mock_adapter_factory()),
        patch("salvo.cli.run_cmd.find_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["run", str(scenario_file), "-n", "1"])

    assert result.exit_code == 0, f"Output: {result.output}"

    # Check persisted TrialSuiteResult
    runs_dir = tmp_path / ".salvo" / "runs"
    run_files = [f for f in runs_dir.glob("*.json") if f.name != "latest"]
    assert len(run_files) == 1

    data = json.loads(run_files[0].read_text())
    assert data["verdict"] == "PASS"
    assert data["score_avg"] == 1.0
    assert len(data["trials"]) == 1
    assert data["trials"][0]["score"] == 1.0
    assert len(data["trials"][0]["eval_results"]) == 1
    assert data["trials"][0]["eval_results"][0]["assertion_type"] == "jmespath"
    assert data["trials"][0]["eval_results"][0]["passed"] is True
