"""Pydantic models for recorded traces and re-evaluation results.

Defines the schema for recorded trace files that capture full agent
execution traces with metadata for replay and re-evaluation, plus
RevalResult for re-evaluation output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult

# Current schema version for recorded trace files.
CURRENT_TRACE_SCHEMA_VERSION = 1


class TraceMetadata(BaseModel):
    """Metadata attached to a recorded trace.

    Captures recording context: schema version, recording mode,
    salvo version, timestamps, and source run information.
    """

    model_config = {"extra": "forbid"}

    schema_version: int = 1
    recording_mode: Literal["full", "metadata_only"] = "full"
    salvo_version: str
    recorded_at: datetime
    source_run_id: str
    scenario_name: str
    scenario_file: str
    scenario_hash: str


class RecordedTrace(BaseModel):
    """A complete recorded trace wrapping a RunTrace with metadata.

    Contains the execution trace, recording metadata, a snapshot of
    the scenario configuration, and an optional link to the original
    trace for re-evaluation results.
    """

    model_config = {"extra": "forbid"}

    metadata: TraceMetadata
    trace: RunTrace
    scenario_snapshot: dict[str, Any]
    original_trace_id: str | None = None


class RevalResult(BaseModel):
    """Result of re-evaluating a recorded trace with updated assertions.

    Links back to the original trace via original_trace_id and stores
    new evaluation results, score, and pass/fail status.
    """

    model_config = {"extra": "forbid"}

    reeval_id: str
    original_trace_id: str
    scenario_name: str
    scenario_file: str | None = None
    eval_results: list[EvalResult]
    score: float
    passed: bool
    threshold: float
    evaluated_at: datetime
    assertions_used: int
    assertions_skipped: int = 0


def validate_trace_version(metadata: TraceMetadata) -> None:
    """Validate that a trace's schema version is supported.

    Raises ValueError if the trace was created by a newer version
    of Salvo that uses a schema version we don't understand.

    Args:
        metadata: The trace metadata to validate.

    Raises:
        ValueError: If schema_version exceeds CURRENT_TRACE_SCHEMA_VERSION.
    """
    if metadata.schema_version > CURRENT_TRACE_SCHEMA_VERSION:
        raise ValueError(
            f"Trace schema version {metadata.schema_version} is newer than "
            f"supported version {CURRENT_TRACE_SCHEMA_VERSION}. "
            f"Please upgrade Salvo to read this trace."
        )
