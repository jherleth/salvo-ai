"""Tests for judge structured output extraction."""

from __future__ import annotations

import json

from salvo.adapters.base import AdapterTurnResult, TokenUsage, ToolCallResult
from salvo.evaluation.judge.extraction import (
    extract_json_from_text,
    extract_scores,
    extract_scores_from_tool_call,
)


SAMPLE_CRITERIA = [
    {"name": "accuracy", "description": "Factually correct", "weight": 1.0},
    {"name": "clarity", "description": "Easy to understand", "weight": 0.5},
]


def _make_tool_call(name: str, arguments: dict) -> ToolCallResult:
    return ToolCallResult(id="call_123", name=name, arguments=arguments)


def _make_result(
    content: str | None = None,
    tool_calls: list | None = None,
) -> AdapterTurnResult:
    return AdapterTurnResult(
        content=content,
        tool_calls=tool_calls or [],
        usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        raw_response={},
        finish_reason="stop",
    )


class TestExtractFromToolCall:
    def test_extract_from_tool_call_valid(self):
        tool_calls = [
            _make_tool_call(
                "score_criteria",
                {
                    "accuracy": {"score": 0.9, "reasoning": "Good"},
                    "clarity": {"score": 0.7, "reasoning": "Clear"},
                },
            )
        ]
        result = extract_scores_from_tool_call(tool_calls, SAMPLE_CRITERIA)
        assert result is not None
        assert result["accuracy"]["score"] == 0.9
        assert result["clarity"]["score"] == 0.7

    def test_extract_from_tool_call_clamps_out_of_range(self):
        tool_calls = [
            _make_tool_call(
                "score_criteria",
                {
                    "accuracy": {"score": 1.5, "reasoning": "Over"},
                    "clarity": {"score": -0.3, "reasoning": "Under"},
                },
            )
        ]
        result = extract_scores_from_tool_call(tool_calls, SAMPLE_CRITERIA)
        assert result is not None
        assert result["accuracy"]["score"] == 1.0
        assert result["clarity"]["score"] == 0.0

    def test_extract_from_tool_call_no_match(self):
        tool_calls = [
            _make_tool_call("other_tool", {"foo": "bar"})
        ]
        result = extract_scores_from_tool_call(tool_calls, SAMPLE_CRITERIA)
        assert result is None


class TestExtractJsonFromText:
    def test_extract_json_from_text_direct(self):
        text = json.dumps({"accuracy": {"score": 0.8, "reasoning": "ok"}})
        result = extract_json_from_text(text)
        assert result is not None
        assert result["accuracy"]["score"] == 0.8

    def test_extract_json_from_text_brace(self):
        text = 'Here are my scores: {"accuracy": {"score": 0.8, "reasoning": "ok"}} done.'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["accuracy"]["score"] == 0.8

    def test_extract_json_from_text_code_block(self):
        text = 'Here are scores:\n```json\n{"accuracy": {"score": 0.8, "reasoning": "ok"}}\n```'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["accuracy"]["score"] == 0.8

    def test_extract_json_from_text_invalid(self):
        result = extract_json_from_text("This is not JSON at all")
        assert result is None


class TestExtractScores:
    def test_extract_scores_prefers_tool_call(self):
        tool_calls = [
            _make_tool_call(
                "score_criteria",
                {
                    "accuracy": {"score": 0.9, "reasoning": "Good"},
                    "clarity": {"score": 0.8, "reasoning": "Clear"},
                },
            )
        ]
        # Also provide text JSON -- tool call should win
        text = json.dumps({
            "accuracy": {"score": 0.1, "reasoning": "Bad"},
            "clarity": {"score": 0.1, "reasoning": "Bad"},
        })
        result_obj = _make_result(content=text, tool_calls=tool_calls)
        result = extract_scores(result_obj, SAMPLE_CRITERIA)
        assert result is not None
        assert result["accuracy"]["score"] == 0.9  # from tool call, not text

    def test_extract_scores_falls_back_to_text(self):
        text = json.dumps({
            "accuracy": {"score": 0.7, "reasoning": "Decent"},
            "clarity": {"score": 0.6, "reasoning": "OK"},
        })
        result_obj = _make_result(content=text, tool_calls=[])
        result = extract_scores(result_obj, SAMPLE_CRITERIA)
        assert result is not None
        assert result["accuracy"]["score"] == 0.7

    def test_extract_scores_both_fail(self):
        result_obj = _make_result(content="No scores here", tool_calls=[])
        result = extract_scores(result_obj, SAMPLE_CRITERIA)
        assert result is None
