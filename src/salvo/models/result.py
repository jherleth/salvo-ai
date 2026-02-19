"""Result data models for Salvo run outputs.

These models encode the execution output contract, capturing
run metadata, individual evaluation results, and aggregate scores.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunMetadata(BaseModel):
    """Metadata about a single scenario run."""

    scenario_name: str
    scenario_file: str
    scenario_hash: str
    timestamp: datetime
    model: str
    adapter: str
    salvo_version: str
    passed: bool
    score: float
    cost_usd: float | None = None
    latency_seconds: float | None = None


class EvalResult(BaseModel):
    """Result of evaluating a single assertion against a run."""

    assertion_type: str
    score: float
    passed: bool
    weight: float
    required: bool
    details: str = ""
    metadata: dict[str, Any] | None = None


class RunResult(BaseModel):
    """Complete result of a single scenario run.

    Contains metadata, individual eval results, and aggregate scoring.
    Designed for JSON serialization and lossless round-trip deserialization.
    """

    run_id: str
    metadata: RunMetadata
    eval_results: list[EvalResult] = []
    score: float
    passed: bool
    trace_id: str | None = None
