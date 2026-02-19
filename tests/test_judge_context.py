"""Tests for judge trace context builder."""

from __future__ import annotations

from datetime import datetime

from salvo.evaluation.judge.context import build_context, build_tool_call_summary
from salvo.execution.trace import RunTrace
from salvo.models.scenario import Scenario


def _make_trace(
    final_content: str | None = "Agent response here",
    tool_calls_made: list | None = None,
) -> RunTrace:
    """Create a minimal RunTrace for testing."""
    return RunTrace(
        messages=[],
        tool_calls_made=tool_calls_made or [],
        turn_count=1,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        latency_seconds=1.0,
        final_content=final_content,
        finish_reason="stop",
        model="gpt-4o",
        provider="openai",
        timestamp=datetime.now(),
        scenario_hash="abc123",
    )


def _make_scenario(
    system_prompt: str = "You are a helpful assistant.",
    tools: list | None = None,
) -> Scenario:
    """Create a minimal Scenario for testing."""
    from salvo.models.scenario import ToolDef

    return Scenario(
        model="gpt-4o",
        prompt="Test prompt",
        system_prompt=system_prompt,
        tools=tools or [],
    )


class TestBuildToolCallSummary:
    def test_build_tool_call_summary_no_calls(self):
        trace = _make_trace(tool_calls_made=[])
        result = build_tool_call_summary(trace)
        assert result == "No tool calls were made."

    def test_build_tool_call_summary_truncates_long_args(self):
        long_args = "a" * 200
        trace = _make_trace(
            tool_calls_made=[
                {"name": "search", "arguments": {"query": long_args}}
            ]
        )
        result = build_tool_call_summary(trace, max_arg_length=100)
        assert "search" in result
        assert "..." in result
        # The truncated string should be at most max_arg_length + "..."
        # Check that the full 200-char string is NOT present
        assert long_args not in result


class TestBuildContext:
    def test_build_context_default(self):
        trace = _make_trace(
            final_content="Final answer",
            tool_calls_made=[{"name": "lookup", "arguments": {"id": "123"}}],
        )
        result = build_context(trace)
        assert "## Agent's Final Response" in result
        assert "Final answer" in result
        assert "## Tool Calls Made" in result
        assert "lookup" in result

    def test_build_context_empty_response(self):
        trace = _make_trace(final_content=None)
        result = build_context(trace)
        assert "(empty)" in result

    def test_build_context_with_system_prompt(self):
        trace = _make_trace()
        scenario = _make_scenario(system_prompt="Be helpful and concise.")
        result = build_context(trace, scenario=scenario, include_system_prompt=True)
        assert "## Scenario System Prompt" in result
        assert "Be helpful and concise." in result

    def test_build_context_truncates_long_system_prompt(self):
        long_prompt = "x" * 3000
        trace = _make_trace()
        scenario = _make_scenario(system_prompt=long_prompt)
        result = build_context(trace, scenario=scenario, include_system_prompt=True)
        assert "## Scenario System Prompt" in result
        # Should be truncated to 2000 chars
        assert long_prompt not in result
        assert "..." in result
