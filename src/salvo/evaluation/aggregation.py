"""Aggregate metrics computation and cross-trial failure ranking.

Computes percentile-based score/latency/cost statistics across
multiple trial results and ranks assertion failures by frequency
and weighted impact.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from salvo.models.trial import TrialResult, Verdict


def compute_aggregate_metrics(
    scored_trials: list[TrialResult],
    threshold: float,
) -> dict:
    """Compute aggregate score, latency, and cost metrics across trials.

    Uses statistics.quantiles for percentile computation. Guards
    against 0-trial and 1-trial edge cases (quantiles requires >= 2).

    Args:
        scored_trials: List of completed TrialResult objects with scores.
        threshold: Score threshold for pass/fail determination.

    Returns:
        Dict with score_avg, score_min, score_p50, score_p95,
        pass_rate, latency_p50, latency_p95, cost_total,
        cost_avg_per_trial.
    """
    if not scored_trials:
        return {
            "score_avg": 0.0,
            "score_min": 0.0,
            "score_p50": 0.0,
            "score_p95": 0.0,
            "pass_rate": 0.0,
            "latency_p50": None,
            "latency_p95": None,
            "cost_total": None,
            "cost_avg_per_trial": None,
        }

    scores = [t.score for t in scored_trials]
    latencies = [t.latency_seconds for t in scored_trials]
    costs = [t.cost_usd for t in scored_trials if t.cost_usd is not None]

    n = len(scored_trials)
    score_avg = sum(scores) / n
    score_min = min(scores)
    passed_count = sum(1 for t in scored_trials if t.passed)
    pass_rate = passed_count / n

    if n == 1:
        # statistics.quantiles requires >= 2 data points
        score_p50 = scores[0]
        score_p95 = scores[0]
        latency_p50 = latencies[0]
        latency_p95 = latencies[0]
    else:
        # quantiles(n=100) gives 99 cut points -> index 49 is p50, 94 is p95
        score_quantiles = statistics.quantiles(scores, n=100)
        score_p50 = score_quantiles[49]
        score_p95 = score_quantiles[94]
        latency_quantiles = statistics.quantiles(latencies, n=100)
        latency_p50 = latency_quantiles[49]
        latency_p95 = latency_quantiles[94]

    cost_total: float | None = None
    cost_avg_per_trial: float | None = None
    if costs:
        cost_total = sum(costs)
        cost_avg_per_trial = cost_total / n

    return {
        "score_avg": score_avg,
        "score_min": score_min,
        "score_p50": score_p50,
        "score_p95": score_p95,
        "pass_rate": pass_rate,
        "latency_p50": latency_p50,
        "latency_p95": latency_p95,
        "cost_total": cost_total,
        "cost_avg_per_trial": cost_avg_per_trial,
    }


def determine_verdict(
    trials: list[TrialResult],
    avg_score: float,
    threshold: float,
    allow_infra: bool = False,
) -> Verdict:
    """Determine the overall verdict for a trial suite.

    Priority order:
    1. Any INFRA_ERROR (and not allow_infra) -> INFRA_ERROR
    2. Any hard_fail -> HARD FAIL
    3. avg_score < threshold and pass_rate > 0 -> PARTIAL
    4. avg_score < threshold and pass_rate == 0 -> FAIL
    5. avg_score >= threshold -> PASS

    Args:
        trials: List of completed TrialResult objects.
        avg_score: Average score across scored trials.
        threshold: Score threshold for pass/fail.
        allow_infra: If True, ignore INFRA_ERROR trials in verdict.

    Returns:
        Verdict enum value.
    """
    from salvo.models.trial import TrialStatus, Verdict

    has_infra_error = any(t.status == TrialStatus.infra_error for t in trials)
    has_hard_fail = any(t.status == TrialStatus.hard_fail for t in trials)

    if has_infra_error and not allow_infra:
        return Verdict.INFRA_ERROR

    if has_hard_fail:
        return Verdict.HARD_FAIL

    scored_trials = [
        t for t in trials if t.status != TrialStatus.infra_error
    ]
    passed_count = sum(1 for t in scored_trials if t.passed)
    pass_rate = passed_count / len(scored_trials) if scored_trials else 0.0

    if avg_score < threshold:
        if pass_rate > 0:
            return Verdict.PARTIAL
        return Verdict.FAIL

    return Verdict.PASS


def aggregate_failures(trials: list[TrialResult]) -> list[dict]:
    """Aggregate assertion failures across all trials.

    For each unique failed assertion (by type + expression prefix),
    computes frequency, failure rate, total weight lost, and ranks
    by frequency * average weight lost (descending).

    Args:
        trials: List of completed TrialResult objects.

    Returns:
        List of failure dicts sorted by impact score, each containing:
        assertion_type, expression, fail_count, fail_rate,
        total_weight_lost, sample_details (up to 3).
    """
    total_trials = len(trials)
    if total_trials == 0:
        return []

    # Collect failures keyed by (assertion_type, expression_prefix)
    failure_map: dict[tuple[str, str], dict] = {}

    for trial in trials:
        for er in trial.eval_results:
            if er.passed:
                continue

            expr_key = er.details[:80] if er.details else ""
            key = (er.assertion_type, expr_key)

            if key not in failure_map:
                failure_map[key] = {
                    "assertion_type": er.assertion_type,
                    "expression": expr_key,
                    "fail_count": 0,
                    "total_weight_lost": 0.0,
                    "sample_details": [],
                }

            entry = failure_map[key]
            entry["fail_count"] += 1
            entry["total_weight_lost"] += (1.0 - er.score) * er.weight
            if len(entry["sample_details"]) < 3:
                entry["sample_details"].append(er.details)

    # Compute derived fields and sort
    result = []
    for entry in failure_map.values():
        fc = entry["fail_count"]
        entry["fail_rate"] = fc / total_trials
        avg_weight_lost = entry["total_weight_lost"] / fc if fc > 0 else 0.0
        entry["_impact_score"] = fc * avg_weight_lost
        result.append(entry)

    result.sort(key=lambda x: x["_impact_score"], reverse=True)

    # Remove internal sort key from output
    for entry in result:
        del entry["_impact_score"]

    return result
