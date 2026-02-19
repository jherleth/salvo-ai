"""Evaluator registry -- maps assertion type strings to evaluator classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.evaluation.evaluators.cost_limit import CostLimitEvaluator
from salvo.evaluation.evaluators.jmespath_eval import JMESPathEvaluator
from salvo.evaluation.evaluators.judge import JudgeEvaluator
from salvo.evaluation.evaluators.latency_limit import LatencyLimitEvaluator
from salvo.evaluation.evaluators.tool_sequence import ToolSequenceEvaluator

EVALUATOR_REGISTRY: dict[str, type[BaseEvaluator]] = {
    "jmespath": JMESPathEvaluator,
    "tool_sequence": ToolSequenceEvaluator,
    "cost_limit": CostLimitEvaluator,
    "latency_limit": LatencyLimitEvaluator,
    "judge": JudgeEvaluator,
}


def get_evaluator(assertion_type: str) -> BaseEvaluator:
    """Look up and instantiate an evaluator for the given assertion type.

    Raises:
        ValueError: If *assertion_type* is not in the registry.
    """
    cls = EVALUATOR_REGISTRY.get(assertion_type)
    if cls is None:
        available = sorted(EVALUATOR_REGISTRY.keys())
        raise ValueError(
            f"Unknown assertion type {assertion_type!r}. "
            f"Available types: {available}"
        )
    return cls()
