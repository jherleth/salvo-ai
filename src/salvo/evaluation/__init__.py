"""Evaluation package for assertion processing and scoring.

Provides assertion normalization, evaluator dispatch, and
weighted scoring with required-assertion hard-fail logic.
"""

from __future__ import annotations

from salvo.evaluation.normalizer import normalize_assertion, normalize_assertions
from salvo.evaluation.evaluators import get_evaluator
from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.evaluation.evaluators.jmespath_eval import build_trace_data
from salvo.evaluation.scorer import compute_score, evaluate_trace

__all__ = [
    "normalize_assertion",
    "normalize_assertions",
    "get_evaluator",
    "BaseEvaluator",
    "build_trace_data",
    "compute_score",
    "evaluate_trace",
]
