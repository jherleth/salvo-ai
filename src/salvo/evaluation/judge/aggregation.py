"""k-vote aggregation with median scores and majority verdict.

Aggregates multiple judge votes into per-criterion median scores
and an overall weighted score with majority-vote pass/fail.
"""

from __future__ import annotations

import statistics


def aggregate_k_votes(
    k_results: list[dict],
    criteria: list[dict],
    threshold: float,
) -> tuple[float, bool, list[dict]]:
    """Aggregate k judge votes into a single assertion result.

    For each criterion, collects scores across all k votes and computes
    the median. Then computes a weighted average across criteria.
    Majority vote determines pass/fail: each vote's weighted average
    is compared to threshold, and strict majority must pass.

    Args:
        k_results: List of per-vote dicts mapping criterion names
            to {score, reasoning} dicts.
        criteria: List of criterion dicts with name, description, weight.
        threshold: Minimum weighted average score to count as a pass.

    Returns:
        Tuple of (overall_score, passed, per_criterion_details):
        - overall_score: Weighted average of median per-criterion scores.
        - passed: True if strict majority of votes pass threshold.
        - per_criterion_details: List of dicts with name, median_score,
          all_scores, weight for each criterion.
    """
    if not k_results:
        return (0.0, False, [])

    # Collect per-criterion scores across all votes
    per_criterion: dict[str, list[float]] = {c["name"]: [] for c in criteria}

    for vote in k_results:
        for c in criteria:
            name = c["name"]
            if name in vote and isinstance(vote[name], dict) and "score" in vote[name]:
                per_criterion[name].append(float(vote[name]["score"]))

    # Compute median per criterion
    medians: dict[str, float] = {}
    per_criterion_details: list[dict] = []

    for c in criteria:
        name = c["name"]
        scores = per_criterion[name]
        median = statistics.median(scores) if scores else 0.0
        medians[name] = median
        per_criterion_details.append({
            "name": name,
            "median_score": median,
            "all_scores": scores,
            "weight": c["weight"],
        })

    # Compute weighted average of medians
    total_weight = sum(c["weight"] for c in criteria)
    if total_weight == 0:
        overall_score = 0.0
    else:
        overall_score = sum(
            medians[c["name"]] * c["weight"] for c in criteria
        ) / total_weight

    # Majority vote: compute each vote's weighted average, check threshold
    pass_count = 0
    for vote in k_results:
        vote_total = 0.0
        for c in criteria:
            name = c["name"]
            if name in vote and isinstance(vote[name], dict) and "score" in vote[name]:
                vote_total += float(vote[name]["score"]) * c["weight"]
            # Missing criterion contributes 0.0

        vote_avg = vote_total / total_weight if total_weight > 0 else 0.0
        if vote_avg >= threshold:
            pass_count += 1

    passed = pass_count > len(k_results) / 2

    return (overall_score, passed, per_criterion_details)
