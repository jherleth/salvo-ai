"""Tests for judge prompt template builder."""

from __future__ import annotations

from salvo.evaluation.judge.prompt import (
    build_criteria_block,
    build_judge_prompt,
    build_scoring_tool,
    format_tool_choice,
)


SAMPLE_CRITERIA = [
    {"name": "accuracy", "description": "Factually correct response", "weight": 1.0},
    {"name": "completeness", "description": "Covers all required points", "weight": 0.8},
    {"name": "clarity", "description": "Easy to understand", "weight": 0.5},
]


class TestBuildCriteriaBlock:
    def test_build_criteria_block_formats_all_criteria(self):
        result = build_criteria_block(SAMPLE_CRITERIA)
        assert "accuracy" in result
        assert "completeness" in result
        assert "clarity" in result
        assert "weight: 1.0" in result
        assert "weight: 0.8" in result
        assert "weight: 0.5" in result
        assert "Factually correct response" in result
        assert "Covers all required points" in result
        assert "Easy to understand" in result


class TestBuildJudgePrompt:
    def test_build_judge_prompt_contains_scale(self):
        result = build_judge_prompt(SAMPLE_CRITERIA)
        assert "0.0" in result
        assert "1.0" in result
        # Check for the 5-point anchoring
        assert "0.25" in result
        assert "0.5" in result
        assert "0.75" in result

    def test_build_judge_prompt_contains_criteria(self):
        result = build_judge_prompt(SAMPLE_CRITERIA)
        assert "accuracy" in result
        assert "completeness" in result
        assert "clarity" in result


class TestBuildScoringTool:
    def test_build_scoring_tool_schema(self):
        tool = build_scoring_tool(SAMPLE_CRITERIA)
        assert tool["name"] == "score_criteria"
        assert "description" in tool
        params = tool["parameters"]
        assert params["type"] == "object"
        # Each criterion should be a property
        props = params["properties"]
        assert "accuracy" in props
        assert "completeness" in props
        assert "clarity" in props
        # Each should have score + reasoning sub-properties
        for name in ["accuracy", "completeness", "clarity"]:
            criterion_props = props[name]["properties"]
            assert "score" in criterion_props
            assert "reasoning" in criterion_props
            assert criterion_props["score"]["type"] == "number"
            assert criterion_props["reasoning"]["type"] == "string"
            assert set(props[name]["required"]) == {"score", "reasoning"}
        # All criteria required at top level
        assert set(params["required"]) == {"accuracy", "completeness", "clarity"}


class TestFormatToolChoice:
    def test_format_tool_choice_openai(self):
        result = format_tool_choice("openai", "score_criteria")
        assert result == {
            "tool_choice": {
                "type": "function",
                "function": {"name": "score_criteria"},
            }
        }

    def test_format_tool_choice_anthropic(self):
        result = format_tool_choice("anthropic", "score_criteria")
        assert result == {
            "tool_choice": {"type": "tool", "name": "score_criteria"}
        }

    def test_format_tool_choice_unknown(self):
        result = format_tool_choice("some_other_provider", "score_criteria")
        assert result == {}
