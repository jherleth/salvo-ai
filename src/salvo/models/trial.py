"""Trial data models for N-trial execution results.

These models encode the N-trial execution contract, capturing
individual trial results, aggregate suite metrics, verdicts,
and cross-trial failure rankings.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from salvo.models.result import EvalResult


class TrialStatus(str, Enum):
    """Status of an individual trial execution."""

    passed = "passed"
    failed = "failed"
    hard_fail = "hard_fail"
    infra_error = "infra_error"


class TrialResult(BaseModel):
    """Result of a single trial within an N-trial suite.

    Captures execution outcome, scoring, latency, cost, retry
    information, and individual assertion evaluation results.
    """

    model_config = {"extra": "forbid"}

    trial_number: int
    status: TrialStatus
    score: float
    passed: bool
    eval_results: list[EvalResult] = []
    latency_seconds: float
    cost_usd: float | None = None
    retries_used: int = 0
    transient_error_types: list[str] = Field(default_factory=list)
    error_message: str | None = None
    trace_id: str | None = None


class Verdict(str, Enum):
    """Overall verdict for a trial suite."""

    PASS = "PASS"
    FAIL = "FAIL"
    HARD_FAIL = "HARD FAIL"
    PARTIAL = "PARTIAL"
    INFRA_ERROR = "INFRA_ERROR"


class TrialSuiteResult(BaseModel):
    """Aggregate result of running a scenario N times.

    Contains all individual trial results plus computed aggregate
    metrics, verdict, cost/latency summaries, retry stats, and
    cross-trial assertion failure rankings.
    """

    model_config = {"extra": "forbid"}

    run_id: str
    scenario_name: str
    scenario_file: str
    model: str
    adapter: str

    trials: list[TrialResult]
    trials_total: int
    trials_passed: int
    trials_failed: int
    trials_hard_fail: int
    trials_infra_error: int

    verdict: Verdict
    pass_rate: float

    score_avg: float
    score_min: float
    score_p50: float
    score_p95: float
    threshold: float

    cost_total: float | None = None
    cost_avg_per_trial: float | None = None

    latency_p50: float | None = None
    latency_p95: float | None = None

    total_retries: int = 0
    trials_with_retries: int = 0

    early_stopped: bool = False
    early_stop_reason: str | None = None

    n_requested: int = 3
    assertion_failures: list[dict] = Field(default_factory=list)
