"""Tests for salvo.models.result - RunMetadata, EvalResult, RunResult."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


class TestRunMetadata:
    """Test RunMetadata model."""

    def test_run_metadata_creation(self):
        """RunMetadata with all fields."""
        from salvo.models import RunMetadata

        data = {
            "scenario_name": "fix-tests",
            "scenario_file": "scenarios/fix-tests.yaml",
            "scenario_hash": "abc123",
            "timestamp": "2026-02-17T18:00:00Z",
            "model": "gpt-4o",
            "adapter": "openai",
            "salvo_version": "0.1.0",
            "passed": True,
            "score": 0.9,
            "cost_usd": 0.05,
            "latency_seconds": 2.3,
        }
        meta = RunMetadata.model_validate(data)
        assert meta.scenario_name == "fix-tests"
        assert meta.passed is True
        assert meta.score == 0.9
        assert meta.cost_usd == 0.05
        assert meta.latency_seconds == 2.3

    def test_optional_fields_default_none(self):
        """cost_usd and latency_seconds default to None."""
        from salvo.models import RunMetadata

        data = {
            "scenario_name": "fix-tests",
            "scenario_file": "scenarios/fix-tests.yaml",
            "scenario_hash": "abc123",
            "timestamp": "2026-02-17T18:00:00Z",
            "model": "gpt-4o",
            "adapter": "openai",
            "salvo_version": "0.1.0",
            "passed": True,
            "score": 0.9,
        }
        meta = RunMetadata.model_validate(data)
        assert meta.cost_usd is None
        assert meta.latency_seconds is None


class TestEvalResult:
    """Test EvalResult model."""

    def test_eval_result_creation(self):
        """EvalResult with all fields."""
        from salvo.models import EvalResult

        data = {
            "assertion_type": "tool_call",
            "score": 1.0,
            "passed": True,
            "weight": 2.0,
            "required": True,
            "details": "Tool file_read was called correctly",
        }
        result = EvalResult.model_validate(data)
        assert result.assertion_type == "tool_call"
        assert result.score == 1.0
        assert result.passed is True
        assert result.weight == 2.0
        assert result.required is True
        assert result.details == "Tool file_read was called correctly"


class TestRunResult:
    """Test RunResult model."""

    def _make_run_result_data(self):
        """Helper to create valid RunResult data."""
        return {
            "run_id": "run-001",
            "metadata": {
                "scenario_name": "fix-tests",
                "scenario_file": "scenarios/fix-tests.yaml",
                "scenario_hash": "abc123",
                "timestamp": "2026-02-17T18:00:00Z",
                "model": "gpt-4o",
                "adapter": "openai",
                "salvo_version": "0.1.0",
                "passed": True,
                "score": 0.9,
            },
            "eval_results": [
                {
                    "assertion_type": "tool_call",
                    "score": 1.0,
                    "passed": True,
                    "weight": 1.0,
                    "required": False,
                }
            ],
            "score": 0.9,
            "passed": True,
        }

    def test_run_result_creation(self):
        """RunResult with run_id, metadata, eval_results, score, passed."""
        from salvo.models import RunResult

        data = self._make_run_result_data()
        result = RunResult.model_validate(data)
        assert result.run_id == "run-001"
        assert result.passed is True
        assert result.score == 0.9
        assert len(result.eval_results) == 1

    def test_run_result_json_round_trip(self):
        """RunResult survives JSON serialization round-trip."""
        from salvo.models import RunResult

        data = self._make_run_result_data()
        original = RunResult.model_validate(data)
        json_str = original.model_dump_json()
        restored = RunResult.model_validate_json(json_str)
        assert restored.run_id == original.run_id
        assert restored.score == original.score
        assert restored.passed == original.passed
        assert len(restored.eval_results) == len(original.eval_results)
        assert restored.metadata.scenario_name == original.metadata.scenario_name

    def test_run_result_model_dump_json_mode(self):
        """model_dump(mode='json') serializes datetime correctly."""
        from salvo.models import RunResult

        data = self._make_run_result_data()
        result = RunResult.model_validate(data)
        dumped = result.model_dump(mode="json")
        # timestamp should be a string in JSON mode
        assert isinstance(dumped["metadata"]["timestamp"], str)

    def test_trace_id_defaults_to_none(self):
        """trace_id is optional and defaults to None."""
        from salvo.models import RunResult

        data = self._make_run_result_data()
        result = RunResult.model_validate(data)
        assert result.trace_id is None

    def test_trace_id_can_be_set(self):
        """trace_id can be explicitly provided."""
        from salvo.models import RunResult

        data = self._make_run_result_data()
        data["trace_id"] = "trace-abc-123"
        result = RunResult.model_validate(data)
        assert result.trace_id == "trace-abc-123"
