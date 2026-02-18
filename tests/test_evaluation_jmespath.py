"""Tests for JMESPath evaluator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from salvo.evaluation.evaluators.jmespath_eval import (
    JMESPathEvaluator,
    build_trace_data,
    compare,
)
from salvo.execution.trace import RunTrace, TraceMessage


def _make_trace(**overrides) -> RunTrace:
    """Create a minimal RunTrace for testing."""
    defaults = {
        "messages": [
            TraceMessage(role="user", content="Hello"),
            TraceMessage(role="assistant", content="Hi there!"),
        ],
        "tool_calls_made": [],
        "turn_count": 1,
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "latency_seconds": 0.5,
        "final_content": "Hi there!",
        "finish_reason": "stop",
        "model": "gpt-4",
        "provider": "openai",
        "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "scenario_hash": "abc123",
        "cost_usd": 0.01,
    }
    defaults.update(overrides)
    return RunTrace(**defaults)


class TestBuildTraceData:
    """Test build_trace_data converts RunTrace to queryable dict."""

    def test_response_structure(self) -> None:
        trace = _make_trace()
        data = build_trace_data(trace)
        assert data["response"]["content"] == "Hi there!"
        assert data["response"]["finish_reason"] == "stop"

    def test_metadata_structure(self) -> None:
        trace = _make_trace()
        data = build_trace_data(trace)
        meta = data["metadata"]
        assert meta["model"] == "gpt-4"
        assert meta["provider"] == "openai"
        assert meta["cost_usd"] == 0.01
        assert meta["latency_seconds"] == 0.5
        assert meta["input_tokens"] == 10
        assert meta["output_tokens"] == 20
        assert meta["total_tokens"] == 30
        assert meta["turn_count"] == 1
        assert meta["finish_reason"] == "stop"

    def test_turns_structure(self) -> None:
        trace = _make_trace()
        data = build_trace_data(trace)
        assert len(data["turns"]) == 2
        assert data["turns"][0]["role"] == "user"
        assert data["turns"][1]["role"] == "assistant"

    def test_tool_calls_structure(self) -> None:
        trace = _make_trace(
            tool_calls_made=[
                {"name": "search", "arguments": {"q": "test"}, "result": "ok"}
            ]
        )
        data = build_trace_data(trace)
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["name"] == "search"


class TestCompare:
    """Test the 8 comparison operators."""

    def test_eq_pass(self) -> None:
        assert compare("hello", "eq", "hello") is True

    def test_eq_fail(self) -> None:
        assert compare("hello", "eq", "world") is False

    def test_ne_pass(self) -> None:
        assert compare("hello", "ne", "world") is True

    def test_ne_fail(self) -> None:
        assert compare("hello", "ne", "hello") is False

    def test_gt_pass(self) -> None:
        assert compare(10, "gt", 5) is True

    def test_gt_fail(self) -> None:
        assert compare(5, "gt", 10) is False

    def test_gte_pass_equal(self) -> None:
        assert compare(5, "gte", 5) is True

    def test_gte_pass_greater(self) -> None:
        assert compare(10, "gte", 5) is True

    def test_gte_fail(self) -> None:
        assert compare(3, "gte", 5) is False

    def test_lt_pass(self) -> None:
        assert compare(3, "lt", 5) is True

    def test_lt_fail(self) -> None:
        assert compare(10, "lt", 5) is False

    def test_lte_pass_equal(self) -> None:
        assert compare(5, "lte", 5) is True

    def test_lte_pass_less(self) -> None:
        assert compare(3, "lte", 5) is True

    def test_lte_fail(self) -> None:
        assert compare(10, "lte", 5) is False

    def test_contains_string_pass(self) -> None:
        assert compare("hello world", "contains", "world") is True

    def test_contains_string_fail(self) -> None:
        assert compare("hello world", "contains", "xyz") is False

    def test_contains_list_pass(self) -> None:
        assert compare(["a", "b", "c"], "contains", "b") is True

    def test_contains_list_fail(self) -> None:
        assert compare(["a", "b", "c"], "contains", "z") is False

    def test_regex_pass(self) -> None:
        assert compare("error 404 not found", "regex", r"\d{3}") is True

    def test_regex_fail(self) -> None:
        assert compare("hello world", "regex", r"\d+") is False

    def test_none_actual_returns_false_for_all_operators(self) -> None:
        for op in ["eq", "ne", "gt", "gte", "lt", "lte", "contains", "regex"]:
            assert compare(None, op, "anything") is False, f"Failed for {op}"

    def test_numeric_coercion_int_vs_float(self) -> None:
        assert compare(10, "gt", 5.5) is True
        assert compare("10", "gt", "5") is True

    def test_numeric_coercion_bad_value_returns_false(self) -> None:
        assert compare("not_a_number", "gt", 5) is False

    def test_invalid_regex_returns_false(self) -> None:
        assert compare("test", "regex", "[invalid") is False


class TestJMESPathEvaluator:
    """Test the full JMESPath evaluator."""

    def test_evaluate_passing(self) -> None:
        trace = _make_trace(final_content="Hello World")
        evaluator = JMESPathEvaluator()
        assertion = {
            "type": "jmespath",
            "expression": "response.content",
            "operator": "contains",
            "value": "Hello",
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True
        assert result.score == 1.0
        assert result.assertion_type == "jmespath"
        assert result.weight == 1.0
        assert result.required is False

    def test_evaluate_failing(self) -> None:
        trace = _make_trace(final_content="Goodbye")
        evaluator = JMESPathEvaluator()
        assertion = {
            "type": "jmespath",
            "expression": "response.content",
            "operator": "eq",
            "value": "Hello",
            "weight": 2.0,
            "required": True,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0
        assert result.weight == 2.0
        assert result.required is True

    def test_invalid_jmespath_expression(self) -> None:
        trace = _make_trace()
        evaluator = JMESPathEvaluator()
        assertion = {
            "type": "jmespath",
            "expression": "!!!invalid!!!",
            "operator": "eq",
            "value": "x",
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0
        assert "error" in result.details.lower() or "parse" in result.details.lower()

    def test_evaluate_metadata_query(self) -> None:
        trace = _make_trace(model="gpt-4o")
        evaluator = JMESPathEvaluator()
        assertion = {
            "type": "jmespath",
            "expression": "metadata.model",
            "operator": "eq",
            "value": "gpt-4o",
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is True

    def test_evaluate_path_not_found(self) -> None:
        trace = _make_trace()
        evaluator = JMESPathEvaluator()
        assertion = {
            "type": "jmespath",
            "expression": "nonexistent.path",
            "operator": "eq",
            "value": "x",
            "weight": 1.0,
            "required": False,
        }
        result = evaluator.evaluate(trace, assertion)
        assert result.passed is False
        assert result.score == 0.0
