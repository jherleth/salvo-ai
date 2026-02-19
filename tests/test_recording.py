"""Tests for the recording pipeline (models, redaction, recorder, store)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from salvo.execution.trace import RunTrace, TraceMessage
from salvo.models.scenario import Scenario
from salvo.models.trial import (
    TrialResult,
    TrialStatus,
    TrialSuiteResult,
    Verdict,
)
from salvo.recording.models import (
    CURRENT_TRACE_SCHEMA_VERSION,
    RecordedTrace,
    TraceMetadata,
    validate_trace_version,
)
from salvo.recording.redaction import (
    apply_custom_redaction,
    build_redaction_pipeline,
    strip_content_for_metadata_only,
)
from salvo.recording.recorder import TraceRecorder, load_project_config
from salvo.storage.json_store import RunStore


# -- Fixtures --


def _make_trace(content: str = "Hello", final: str | None = "Done") -> RunTrace:
    """Create a minimal RunTrace for testing."""
    return RunTrace(
        messages=[
            TraceMessage(role="user", content="Prompt"),
            TraceMessage(
                role="assistant",
                content=content,
                tool_calls=[{"id": "tc1", "name": "get_weather", "arguments": '{"city":"NYC"}'}],
            ),
            TraceMessage(role="tool_result", content="Sunny", tool_call_id="tc1", tool_name="get_weather"),
        ],
        tool_calls_made=[{"id": "tc1", "name": "get_weather"}],
        turn_count=1,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_seconds=1.5,
        final_content=final,
        finish_reason="stop",
        model="gpt-4o",
        provider="openai",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scenario_hash="abc123",
        cost_usd=0.01,
    )


def _make_metadata(**overrides) -> TraceMetadata:
    """Create a minimal TraceMetadata for testing."""
    defaults = {
        "schema_version": 1,
        "recording_mode": "full",
        "salvo_version": "0.1.0",
        "recorded_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "source_run_id": "run-001",
        "scenario_name": "test-scenario",
        "scenario_file": "test.yaml",
        "scenario_hash": "abc123",
    }
    defaults.update(overrides)
    return TraceMetadata(**defaults)


def _make_scenario() -> Scenario:
    """Create a minimal Scenario for testing."""
    return Scenario(
        model="gpt-4o",
        prompt="What is the weather?",
        adapter="openai",
    )


def _make_suite(trace_ids: list[str]) -> TrialSuiteResult:
    """Create a minimal TrialSuiteResult for testing."""
    trials = [
        TrialResult(
            trial_number=i + 1,
            status=TrialStatus.passed,
            score=1.0,
            passed=True,
            latency_seconds=1.0,
            cost_usd=0.01,
            trace_id=tid,
        )
        for i, tid in enumerate(trace_ids)
    ]
    return TrialSuiteResult(
        run_id="suite-001",
        scenario_name="test-scenario",
        scenario_file="test.yaml",
        model="gpt-4o",
        adapter="openai",
        trials=trials,
        trials_total=len(trials),
        trials_passed=len(trials),
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
    )


# -- build_redaction_pipeline tests --


class TestBuildRedactionPipeline:
    def test_builtin_patterns_applied(self):
        fn = build_redaction_pipeline()
        result = fn("key sk-abc12345678901234567890 here")
        assert "sk-abc" not in result
        assert "[REDACTED]" in result

    def test_custom_patterns_extend_builtin(self):
        fn = build_redaction_pipeline([r"ssn:\s*\d{3}-\d{2}-\d{4}"])
        result = fn("ssn: 123-45-6789 and key sk-abc12345678901234567890")
        assert "123-45-6789" not in result
        assert "sk-abc" not in result

    def test_invalid_custom_pattern_raises(self):
        with pytest.raises(ValueError, match="Invalid custom redaction pattern"):
            build_redaction_pipeline(["[invalid"])

    def test_no_custom_patterns(self):
        fn = build_redaction_pipeline(None)
        result = fn("no secrets here")
        assert result == "no secrets here"

    def test_anthropic_key_redacted(self):
        fn = build_redaction_pipeline()
        result = fn("key: sk-ant-abcdefghijklmnopqrstuvwx")
        assert "sk-ant-" not in result

    def test_github_pat_redacted(self):
        fn = build_redaction_pipeline()
        result = fn("token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij")
        assert "ghp_" not in result


# -- strip_content_for_metadata_only tests --


class TestStripContentForMetadataOnly:
    def test_content_replaced(self):
        trace = _make_trace(content="Secret agent data")
        stripped = strip_content_for_metadata_only(trace)
        for msg in stripped.messages:
            if msg.content is not None:
                assert msg.content == "[CONTENT_EXCLUDED]"

    def test_structure_preserved(self):
        trace = _make_trace()
        stripped = strip_content_for_metadata_only(trace)
        assert len(stripped.messages) == len(trace.messages)
        assert stripped.messages[0].role == "user"
        assert stripped.messages[1].role == "assistant"
        assert stripped.messages[2].role == "tool_result"
        assert stripped.messages[2].tool_call_id == "tc1"
        assert stripped.messages[2].tool_name == "get_weather"

    def test_tool_call_arguments_excluded(self):
        trace = _make_trace()
        stripped = strip_content_for_metadata_only(trace)
        tc = stripped.messages[1].tool_calls[0]
        assert tc["name"] == "get_weather"
        assert tc["arguments"] == "[CONTENT_EXCLUDED]"

    def test_final_content_set_to_none(self):
        trace = _make_trace(final="Important result")
        stripped = strip_content_for_metadata_only(trace)
        assert stripped.final_content is None

    def test_none_content_stays_none(self):
        trace = RunTrace(
            messages=[TraceMessage(role="system", content=None)],
            tool_calls_made=[],
            turn_count=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            latency_seconds=0,
            final_content=None,
            finish_reason="stop",
            model="gpt-4o",
            provider="openai",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scenario_hash="abc",
        )
        stripped = strip_content_for_metadata_only(trace)
        assert stripped.messages[0].content is None

    def test_tokens_preserved(self):
        trace = _make_trace()
        stripped = strip_content_for_metadata_only(trace)
        assert stripped.input_tokens == trace.input_tokens
        assert stripped.output_tokens == trace.output_tokens
        assert stripped.total_tokens == trace.total_tokens


# -- RecordedTrace round-trip tests --


class TestRecordedTraceRoundTrip:
    def test_json_roundtrip(self):
        trace = _make_trace()
        metadata = _make_metadata()
        recorded = RecordedTrace(
            metadata=metadata,
            trace=trace,
            scenario_snapshot={"model": "gpt-4o", "prompt": "test"},
        )
        json_str = recorded.model_dump_json(indent=2)
        restored = RecordedTrace.model_validate_json(json_str)
        assert restored.metadata.schema_version == 1
        assert restored.metadata.scenario_name == "test-scenario"
        assert len(restored.trace.messages) == 3
        assert restored.scenario_snapshot["model"] == "gpt-4o"

    def test_original_trace_id_preserved(self):
        trace = _make_trace()
        metadata = _make_metadata()
        recorded = RecordedTrace(
            metadata=metadata,
            trace=trace,
            scenario_snapshot={},
            original_trace_id="orig-123",
        )
        json_str = recorded.model_dump_json()
        restored = RecordedTrace.model_validate_json(json_str)
        assert restored.original_trace_id == "orig-123"


# -- validate_trace_version tests --


class TestValidateTraceVersion:
    def test_current_version_ok(self):
        metadata = _make_metadata(schema_version=CURRENT_TRACE_SCHEMA_VERSION)
        validate_trace_version(metadata)  # should not raise

    def test_future_version_raises(self):
        metadata = _make_metadata(schema_version=CURRENT_TRACE_SCHEMA_VERSION + 1)
        with pytest.raises(ValueError, match="newer than supported"):
            validate_trace_version(metadata)

    def test_older_version_ok(self):
        metadata = _make_metadata(schema_version=0)
        validate_trace_version(metadata)  # older versions should load fine


# -- load_project_config tests --


class TestLoadProjectConfig:
    def test_defaults_when_no_file(self, tmp_path):
        config = load_project_config(tmp_path)
        assert config.recording.mode == "full"
        assert config.recording.custom_redaction_patterns == []

    def test_loads_from_yaml(self, tmp_path):
        yaml_content = (
            "default_adapter: openai\n"
            "default_model: gpt-4o\n"
            "recording:\n"
            "  mode: metadata_only\n"
            "  custom_redaction_patterns:\n"
            '    - "ssn:\\\\d+"\n'
        )
        (tmp_path / "salvo.yaml").write_text(yaml_content)
        config = load_project_config(tmp_path)
        assert config.recording.mode == "metadata_only"
        assert len(config.recording.custom_redaction_patterns) == 1


# -- RunStore recorded trace methods tests --


class TestRunStoreRecordedTraces:
    def test_save_and_load_roundtrip(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()
        trace = _make_trace()
        metadata = _make_metadata()
        recorded = RecordedTrace(
            metadata=metadata,
            trace=trace,
            scenario_snapshot={"model": "gpt-4o"},
        )
        store.save_recorded_trace("trace-001", recorded)
        loaded = store.load_recorded_trace("trace-001")
        assert loaded is not None
        assert loaded.metadata.source_run_id == "run-001"
        assert len(loaded.trace.messages) == 3

    def test_load_nonexistent_returns_none(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()
        assert store.load_recorded_trace("nonexistent") is None

    def test_list_recorded_traces(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()
        trace = _make_trace()
        metadata = _make_metadata()
        for tid in ["trace-aaa", "trace-bbb", "trace-ccc"]:
            recorded = RecordedTrace(
                metadata=metadata,
                trace=trace,
                scenario_snapshot={},
            )
            store.save_recorded_trace(tid, recorded)
        ids = store.list_recorded_traces()
        assert ids == ["trace-aaa", "trace-bbb", "trace-ccc"]

    def test_latest_recorded_symlink(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()
        trace = _make_trace()
        metadata = _make_metadata()
        recorded = RecordedTrace(
            metadata=metadata,
            trace=trace,
            scenario_snapshot={},
        )
        store.save_recorded_trace("trace-001", recorded)
        store.update_latest_recorded_symlink("trace-001")
        latest = store.load_latest_recorded_trace()
        assert latest is not None
        assert latest.metadata.source_run_id == "run-001"

    def test_latest_recorded_returns_none_when_empty(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()
        assert store.load_latest_recorded_trace() is None


# -- TraceRecorder tests --


class TestTraceRecorder:
    def test_record_suite_creates_files(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()

        # Pre-save raw traces
        trace = _make_trace()
        store.save_trace("tid-001", trace)
        store.save_trace("tid-002", trace)

        suite = _make_suite(["tid-001", "tid-002"])
        scenario = _make_scenario()

        recorder = TraceRecorder(
            store=store,
            project_root=tmp_path,
        )
        recorded_ids = recorder.record_suite(suite, scenario, "test.yaml")

        assert recorded_ids == ["tid-001", "tid-002"]
        assert store.load_recorded_trace("tid-001") is not None
        assert store.load_recorded_trace("tid-002") is not None

    def test_record_suite_skips_missing_traces(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()

        # Only save one trace
        trace = _make_trace()
        store.save_trace("tid-001", trace)

        suite = _make_suite(["tid-001", "tid-missing"])
        scenario = _make_scenario()

        recorder = TraceRecorder(store=store, project_root=tmp_path)
        recorded_ids = recorder.record_suite(suite, scenario, "test.yaml")

        assert recorded_ids == ["tid-001"]

    def test_record_suite_metadata_only_mode(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()

        trace = _make_trace(content="Secret data")
        store.save_trace("tid-001", trace)

        suite = _make_suite(["tid-001"])
        scenario = _make_scenario()

        recorder = TraceRecorder(
            store=store,
            project_root=tmp_path,
            recording_mode="metadata_only",
        )
        recorder.record_suite(suite, scenario, "test.yaml")

        loaded = store.load_recorded_trace("tid-001")
        assert loaded is not None
        assert loaded.metadata.recording_mode == "metadata_only"
        for msg in loaded.trace.messages:
            if msg.content is not None:
                assert msg.content == "[CONTENT_EXCLUDED]"
        assert loaded.trace.final_content is None

    def test_record_suite_applies_custom_redaction(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()

        trace = _make_trace(content="My ssn: 123-45-6789")
        store.save_trace("tid-001", trace)

        suite = _make_suite(["tid-001"])
        scenario = _make_scenario()

        recorder = TraceRecorder(
            store=store,
            project_root=tmp_path,
            custom_patterns=[r"ssn:\s*\d{3}-\d{2}-\d{4}"],
        )
        recorder.record_suite(suite, scenario, "test.yaml")

        loaded = store.load_recorded_trace("tid-001")
        assert loaded is not None
        # Check that custom pattern was applied
        for msg in loaded.trace.messages:
            if msg.content and "ssn" in msg.content.lower():
                assert "123-45-6789" not in msg.content

    def test_record_suite_updates_latest_symlink(self, tmp_path):
        store = RunStore(tmp_path)
        store.ensure_dirs()

        trace = _make_trace()
        store.save_trace("tid-001", trace)

        suite = _make_suite(["tid-001"])
        scenario = _make_scenario()

        recorder = TraceRecorder(store=store, project_root=tmp_path)
        recorder.record_suite(suite, scenario, "test.yaml")

        latest = store.load_latest_recorded_trace()
        assert latest is not None


# -- apply_custom_redaction tests --


class TestApplyCustomRedaction:
    def test_redacts_content(self):
        trace = _make_trace(content="key sk-abc12345678901234567890 here")
        fn = build_redaction_pipeline()
        result = apply_custom_redaction(trace, fn)
        assert "sk-abc" not in result.messages[1].content

    def test_redacts_final_content(self):
        trace = _make_trace(final="key sk-abc12345678901234567890 here")
        fn = build_redaction_pipeline()
        result = apply_custom_redaction(trace, fn)
        assert result.final_content is not None
        assert "sk-abc" not in result.final_content
