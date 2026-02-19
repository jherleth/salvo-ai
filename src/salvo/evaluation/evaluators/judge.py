"""JudgeEvaluator -- LLM-as-judge evaluation with k-vote aggregation.

Orchestrates the full judge pipeline: prompt building, adapter calls,
score extraction, and aggregation into a single EvalResult.
"""

from __future__ import annotations

import asyncio
from typing import Any

from salvo.adapters.base import AdapterConfig, Message
from salvo.adapters.registry import get_adapter
from salvo.evaluation.evaluators.base import BaseEvaluator
from salvo.evaluation.judge.aggregation import aggregate_k_votes
from salvo.evaluation.judge.context import build_context
from salvo.evaluation.judge.extraction import extract_scores
from salvo.evaluation.judge.prompt import (
    JUDGE_USER_TEMPLATE,
    build_judge_prompt,
    build_scoring_tool,
    format_tool_choice,
)
from salvo.execution.cost import estimate_cost
from salvo.execution.trace import RunTrace
from salvo.models.result import EvalResult


# Hard-coded defaults for judge configuration
_DEFAULTS = {
    "judge_adapter": "openai",
    "judge_model": "gpt-4o-mini",
    "k": 3,
    "temperature": 0.0,
    "max_tokens": 1024,
}


def resolve_judge_config(
    assertion: dict,
    project_config: dict | None = None,
) -> dict:
    """Merge judge configuration from assertion, project, and defaults.

    Resolution order: assertion-level override > project-level judge
    section > hard-coded defaults.

    Args:
        assertion: The assertion dict (may contain judge_model, k, etc.).
        project_config: Optional project-level judge config dict with
            adapter, model, k, temperature, max_tokens keys.

    Returns:
        Dict with resolved judge_adapter, judge_model, k, temperature,
        max_tokens values.
    """
    result = dict(_DEFAULTS)

    # Apply project-level overrides
    if project_config:
        if "adapter" in project_config:
            result["judge_adapter"] = project_config["adapter"]
        if "model" in project_config:
            result["judge_model"] = project_config["model"]
        if "k" in project_config:
            result["k"] = project_config["k"]
        if "temperature" in project_config:
            result["temperature"] = project_config["temperature"]
        if "max_tokens" in project_config:
            result["max_tokens"] = project_config["max_tokens"]

    # Apply assertion-level overrides (highest priority)
    if "judge_adapter" in assertion:
        result["judge_adapter"] = assertion["judge_adapter"]
    if "judge_model" in assertion:
        result["judge_model"] = assertion["judge_model"]
    if "k" in assertion and assertion["k"] is not None:
        result["k"] = assertion["k"]
    if "temperature" in assertion and assertion["temperature"] is not None:
        result["temperature"] = assertion["temperature"]
    if "max_tokens" in assertion and assertion["max_tokens"] is not None:
        result["max_tokens"] = assertion["max_tokens"]

    return result


class JudgeEvaluator(BaseEvaluator):
    """LLM-as-judge evaluator with k-vote aggregation.

    Uses a separate LLM call to evaluate the agent's response against
    named criteria. Runs k independent evaluations, extracts per-criterion
    scores via structured tool output (with text-JSON fallback), and
    aggregates using median scores and majority-vote pass/fail.
    """

    def evaluate(self, trace: RunTrace, assertion: dict) -> EvalResult:
        """Sync entry point -- delegates to evaluate_async.

        Detects whether an event loop is already running. If not, uses
        asyncio.run(). If already in a loop, raises RuntimeError.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            raise RuntimeError(
                "JudgeEvaluator.evaluate() called from within an async context. "
                "Use evaluate_async() instead."
            )

        return asyncio.run(self.evaluate_async(trace, assertion))

    async def evaluate_async(
        self, trace: RunTrace, assertion: dict
    ) -> EvalResult:
        """Evaluate an assertion using the LLM judge pipeline.

        Args:
            trace: The captured run trace.
            assertion: Canonical assertion dict with criteria, judge_model, etc.

        Returns:
            EvalResult with judge evaluation score and details.
        """
        # Extract assertion parameters
        criteria = assertion.get("criteria", [])
        weight = assertion.get("weight", 1.0)
        required = assertion.get("required", False)
        include_sp = assertion.get("include_system_prompt", False)
        custom_prompt = assertion.get("custom_prompt")

        # Extract injected project judge config and verbose flag
        project_judge_dict = assertion.pop("_project_judge_config", None)
        verbose = assertion.pop("_verbose", False)

        # Resolve default_threshold from project config
        default_threshold = 0.8
        if project_judge_dict and "default_threshold" in project_judge_dict:
            default_threshold = project_judge_dict["default_threshold"]
        threshold = assertion.get("threshold", default_threshold)

        # Resolve judge config (merge defaults with project config)
        config = resolve_judge_config(assertion, project_config=project_judge_dict)
        judge_model = config["judge_model"]
        k = config["k"]
        judge_adapter_name = config["judge_adapter"]
        temperature = config["temperature"]
        max_tokens = config["max_tokens"]

        # Warn when k=1 disables majority voting (verbose-only)
        if k == 1 and verbose:
            import sys

            print(
                f"[salvo] warning: k=1 for judge assertion '{assertion.get('name', '?')}' "
                "-- majority voting is disabled",
                file=sys.stderr,
            )

        # Build context and prompts
        scenario = assertion.get("_scenario")
        context_block = build_context(
            trace, scenario=scenario, include_system_prompt=include_sp
        )

        system_prompt = custom_prompt if custom_prompt else build_judge_prompt(criteria)
        user_prompt = JUDGE_USER_TEMPLATE.format(context_block=context_block)
        scoring_tool = build_scoring_tool(criteria)

        # Resolve adapter
        adapter = get_adapter(judge_adapter_name)
        provider = adapter.provider_name()

        # Build tool_choice extras
        tool_choice_extras = format_tool_choice(provider, "score_criteria")

        # Build adapter config
        adapter_config = AdapterConfig(
            model=judge_model,
            temperature=temperature,
            max_tokens=max_tokens,
            extras=tool_choice_extras,
        )

        # Run k judge calls
        k_results: list[dict] = []
        parse_failures = 0
        total_judge_cost = 0.0

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        for _ in range(k):
            try:
                result = await adapter.send_turn(
                    messages, tools=[scoring_tool], config=adapter_config
                )

                # Track cost
                cost = estimate_cost(
                    judge_model,
                    result.usage.input_tokens,
                    result.usage.output_tokens,
                )
                if cost is not None:
                    total_judge_cost += cost

                # Extract scores
                scores = extract_scores(result, criteria)
                if scores is not None:
                    k_results.append(scores)
                else:
                    parse_failures += 1
            except Exception:
                parse_failures += 1

        # All calls failed
        if not k_results:
            return EvalResult(
                assertion_type="judge",
                score=0.0,
                passed=False,
                weight=weight,
                required=required,
                details=(
                    f"judge_parse_failed: {parse_failures}/{k} calls failed"
                ),
                metadata={
                    "judge_model": judge_model,
                    "judge_k": k,
                    "judge_cost_usd": total_judge_cost,
                },
            )

        # Aggregate results
        overall_score, majority_passed, per_criterion_details = aggregate_k_votes(
            k_results, criteria, threshold
        )

        # Build details string
        criterion_summary = ", ".join(
            f"{d['name']}={d['median_score']:.2f}" for d in per_criterion_details
        )
        details = (
            f"judge={judge_model} k={k} votes={len(k_results)}/{k} | "
            f"judge_cost=${total_judge_cost:.6f} | "
            f"{criterion_summary}"
        )

        return EvalResult(
            assertion_type="judge",
            score=overall_score,
            passed=majority_passed,
            weight=weight,
            required=required,
            details=details,
            metadata={
                "judge_model": judge_model,
                "judge_k": k,
                "judge_cost_usd": total_judge_cost,
                "per_criterion": per_criterion_details,
            },
        )
