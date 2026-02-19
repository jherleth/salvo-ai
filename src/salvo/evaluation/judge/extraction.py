"""Structured output extraction with text-JSON fallback.

Extracts per-criterion scores from LLM judge responses, trying
tool_call arguments first and falling back to text-based JSON extraction.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from salvo.adapters.base import AdapterTurnResult, ToolCallResult


def extract_scores_from_tool_call(
    tool_calls: list[ToolCallResult],
    criteria: list[dict],
) -> dict | None:
    """Extract per-criterion scores from tool call arguments.

    Looks for a tool call named 'score_criteria', parses its arguments,
    and clamps scores to [0.0, 1.0].

    Args:
        tool_calls: List of ToolCallResult from the adapter response.
        criteria: List of criterion dicts with name field.

    Returns:
        Parsed dict mapping criterion names to {score, reasoning},
        or None if no matching tool call found.
    """
    for tc in tool_calls:
        if tc.name == "score_criteria":
            args = tc.arguments
            if not isinstance(args, dict):
                continue

            # Clamp scores to [0.0, 1.0]
            for key, val in args.items():
                if isinstance(val, dict) and "score" in val:
                    score = val["score"]
                    if isinstance(score, (int, float)):
                        val["score"] = max(0.0, min(1.0, float(score)))

            return args

    return None


def extract_json_from_text(text: str) -> dict | None:
    """Fallback: extract JSON from text response.

    Tries three strategies in order:
    1. Direct json.loads on the full text
    2. Brace extraction (first '{' to last '}')
    3. Markdown code block (```json...```)

    Args:
        text: Raw text content from the LLM response.

    Returns:
        Parsed dict or None if all strategies fail.
    """
    if not text:
        return None

    # Strategy 1: direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: brace extraction
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            result = json.loads(text[first_brace : last_brace + 1])
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: markdown code block
    match = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def extract_scores(
    result: AdapterTurnResult,
    criteria: list[dict],
) -> dict | None:
    """Main entry point: extract per-criterion scores from adapter result.

    Tries tool_call extraction first, then text-JSON fallback.
    Validates that the result contains at least one expected criterion name.

    Args:
        result: AdapterTurnResult from the judge LLM call.
        criteria: List of criterion dicts with name field.

    Returns:
        Dict mapping criterion names to {score, reasoning},
        or None if extraction fails.
    """
    criterion_names = {c["name"] for c in criteria}

    # Try tool call extraction first
    if result.tool_calls:
        scores = extract_scores_from_tool_call(result.tool_calls, criteria)
        if scores is not None:
            # Validate at least one expected criterion
            if any(name in scores for name in criterion_names):
                return scores

    # Try text-JSON fallback
    if result.content:
        scores = extract_json_from_text(result.content)
        if scores is not None:
            # Validate at least one expected criterion
            if any(name in scores for name in criterion_names):
                return scores

    return None
