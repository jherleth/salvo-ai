"""Base evaluator abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


class BaseEvaluator(ABC):
    """Abstract base class for assertion evaluators.

    Each evaluator receives a RunTrace and a canonical assertion dict
    and returns an EvalResult.
    """

    @abstractmethod
    def evaluate(self, trace: RunTrace, assertion: dict) -> EvalResult:
        """Evaluate a single assertion against a run trace.

        Args:
            trace: The captured run trace.
            assertion: Canonical assertion dict (already normalized).

        Returns:
            EvalResult with score, passed, weight, required, and details.
        """

    async def evaluate_async(
        self, trace: RunTrace, assertion: dict
    ) -> EvalResult:
        """Async evaluation. Default delegates to sync evaluate().

        Subclasses that need async (e.g., JudgeEvaluator) override this
        method with their async implementation.
        """
        return self.evaluate(trace, assertion)
