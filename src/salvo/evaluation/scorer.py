"""Weighted scorer with required-assertion hard-fail logic.

Computes weighted average scores and determines pass/fail based on
threshold and required assertion constraints.
"""

from __future__ import annotations

from salvo.evaluation.evaluators import get_evaluator
from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


def compute_score(
    eval_results: list[EvalResult],
    threshold: float,
) -> tuple[float, bool, bool]:
    """Compute weighted score from evaluation results.

    Args:
        eval_results: List of individual assertion evaluation results.
        threshold: Minimum score to pass (0.0 to 1.0).

    Returns:
        Tuple of (score, passed, hard_fail):
        - score: Weighted average of individual scores.
        - passed: True if score >= threshold and no hard_fail.
        - hard_fail: True if any required assertion failed.
    """
    if not eval_results:
        return (1.0, True, False)

    hard_fail = any(r.required and not r.passed for r in eval_results)

    total_weight = sum(r.weight for r in eval_results)
    if total_weight == 0:
        return (0.0, False, hard_fail)

    score = sum(r.score * r.weight for r in eval_results) / total_weight
    passed = score >= threshold and not hard_fail

    return (score, passed, hard_fail)


def evaluate_trace(
    trace: RunTrace,
    assertions: list[dict],
    threshold: float,
) -> tuple[list[EvalResult], float, bool]:
    """Orchestrate full evaluation: run evaluators and compute score.

    Takes already-normalized assertions. Normalization happens upstream
    in the pipeline.

    Args:
        trace: The captured run trace.
        assertions: List of canonical assertion dicts (already normalized).
        threshold: Minimum weighted score to pass.

    Returns:
        Tuple of (eval_results, score, passed).
    """
    eval_results: list[EvalResult] = []

    for assertion in assertions:
        evaluator = get_evaluator(assertion["type"])
        result = evaluator.evaluate(trace, assertion)
        eval_results.append(result)

    score, passed, _ = compute_score(eval_results, threshold)

    return (eval_results, score, passed)


async def evaluate_trace_async(
    trace: RunTrace,
    assertions: list[dict],
    threshold: float,
) -> tuple[list[EvalResult], float, bool]:
    """Async evaluation orchestration -- supports async evaluators.

    Same contract as evaluate_trace but awaits evaluate_async() on
    each evaluator, enabling JudgeEvaluator to make LLM calls.

    Args:
        trace: The captured run trace.
        assertions: List of canonical assertion dicts (already normalized).
        threshold: Minimum weighted score to pass.

    Returns:
        Tuple of (eval_results, score, passed).
    """
    eval_results: list[EvalResult] = []

    for assertion in assertions:
        evaluator = get_evaluator(assertion["type"])
        result = await evaluator.evaluate_async(trace, assertion)
        eval_results.append(result)

    score, passed, _ = compute_score(eval_results, threshold)

    return (eval_results, score, passed)
