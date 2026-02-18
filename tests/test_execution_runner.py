"""Tests for ScenarioRunner with mock adapter."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)
from salvo.execution.runner import ScenarioRunner, ToolMockNotFoundError
from salvo.models.scenario import Scenario, ToolDef


class MockAdapter(BaseAdapter):
    """Test adapter that returns pre-configured responses per turn.

    Responses are popped from the list on each send_turn call.
    """

    def __init__(self, responses: list[AdapterTurnResult]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def send_turn(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        config: AdapterConfig | None = None,
    ) -> AdapterTurnResult:
        if self._call_count >= len(self._responses):
            raise RuntimeError("MockAdapter exhausted all pre-configured responses")
        result = self._responses[self._call_count]
        self._call_count += 1
        return result

    def provider_name(self) -> str:
        return "MockAdapter"


def _make_scenario(**kwargs: Any) -> Scenario:
    """Create a minimal scenario with defaults."""
    defaults: dict[str, Any] = {
        "model": "gpt-4o",
        "prompt": "Hello",
    }
    defaults.update(kwargs)
    return Scenario(**defaults)


def _make_config(model: str = "gpt-4o") -> AdapterConfig:
    """Create a minimal adapter config."""
    return AdapterConfig(model=model)


@pytest.mark.asyncio
async def test_runner_single_turn_text_response():
    """Adapter returns text (no tool calls), runner stops, trace has 1 turn."""
    adapter = MockAdapter([
        AdapterTurnResult(
            content="Hello there!",
            tool_calls=[],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_response={},
            finish_reason="stop",
        ),
    ])

    runner = ScenarioRunner(adapter)
    scenario = _make_scenario()
    config = _make_config()

    trace = await runner.run(scenario, config)

    assert trace.turn_count == 1
    assert trace.final_content == "Hello there!"
    assert trace.finish_reason == "stop"
    assert len(trace.tool_calls_made) == 0
    assert trace.input_tokens == 10
    assert trace.output_tokens == 5
    assert trace.total_tokens == 15
    assert trace.max_turns_hit is False
    assert trace.model == "gpt-4o"
    assert trace.provider == "MockAdapter"


@pytest.mark.asyncio
async def test_runner_multi_turn_with_mock_tools():
    """Adapter returns tool_call, runner injects mock, then adapter returns text."""
    adapter = MockAdapter([
        # Turn 1: model calls a tool
        AdapterTurnResult(
            content=None,
            tool_calls=[ToolCallResult(id="tc1", name="search", arguments={"q": "test"})],
            usage=TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
            raw_response={},
            finish_reason="tool_calls",
        ),
        # Turn 2: model gives final answer
        AdapterTurnResult(
            content="Found the result.",
            tool_calls=[],
            usage=TokenUsage(input_tokens=30, output_tokens=15, total_tokens=45),
            raw_response={},
            finish_reason="stop",
        ),
    ])

    runner = ScenarioRunner(adapter)
    scenario = _make_scenario(
        tools=[
            ToolDef(
                name="search",
                description="Search for stuff",
                mock_response="search result data",
            ),
        ],
    )
    config = _make_config()

    trace = await runner.run(scenario, config)

    assert trace.turn_count == 2
    assert trace.final_content == "Found the result."
    assert len(trace.tool_calls_made) == 1
    assert trace.tool_calls_made[0]["name"] == "search"
    assert trace.max_turns_hit is False


@pytest.mark.asyncio
async def test_runner_tool_mock_not_found():
    """Model calls a tool with no mock_response defined -- raises ToolMockNotFoundError."""
    adapter = MockAdapter([
        AdapterTurnResult(
            content=None,
            tool_calls=[ToolCallResult(id="tc1", name="unknown_tool", arguments={})],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_response={},
            finish_reason="tool_calls",
        ),
    ])

    runner = ScenarioRunner(adapter)
    scenario = _make_scenario(
        tools=[
            ToolDef(
                name="search",
                description="Search",
                mock_response="data",
            ),
        ],
    )
    config = _make_config()

    with pytest.raises(ToolMockNotFoundError) as exc_info:
        await runner.run(scenario, config)

    assert exc_info.value.tool_name == "unknown_tool"
    assert "search" in exc_info.value.available_mocks


@pytest.mark.asyncio
async def test_runner_max_turns_safety_net():
    """Adapter always returns tool_calls, runner stops at max_turns."""
    # Create responses that always have tool calls
    responses = [
        AdapterTurnResult(
            content=None,
            tool_calls=[ToolCallResult(id=f"tc{i}", name="search", arguments={"q": "test"})],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_response={},
            finish_reason="tool_calls",
        )
        for i in range(5)
    ]

    adapter = MockAdapter(responses)
    runner = ScenarioRunner(adapter)
    scenario = _make_scenario(
        max_turns=3,
        tools=[
            ToolDef(name="search", description="Search", mock_response="data"),
        ],
    )
    config = _make_config()

    trace = await runner.run(scenario, config)

    assert trace.turn_count == 3
    assert trace.max_turns_hit is True
    assert len(trace.tool_calls_made) == 3  # One tool call per turn


@pytest.mark.asyncio
async def test_runner_parallel_tool_calls():
    """Adapter returns 2 tool_calls at once, both get mock responses."""
    adapter = MockAdapter([
        # Turn 1: model calls two tools at once
        AdapterTurnResult(
            content=None,
            tool_calls=[
                ToolCallResult(id="tc1", name="search", arguments={"q": "a"}),
                ToolCallResult(id="tc2", name="lookup", arguments={"id": "42"}),
            ],
            usage=TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
            raw_response={},
            finish_reason="tool_calls",
        ),
        # Turn 2: final answer
        AdapterTurnResult(
            content="Combined results.",
            tool_calls=[],
            usage=TokenUsage(input_tokens=40, output_tokens=20, total_tokens=60),
            raw_response={},
            finish_reason="stop",
        ),
    ])

    runner = ScenarioRunner(adapter)
    scenario = _make_scenario(
        tools=[
            ToolDef(name="search", description="Search", mock_response="result A"),
            ToolDef(name="lookup", description="Lookup", mock_response={"data": "B"}),
        ],
    )
    config = _make_config()

    trace = await runner.run(scenario, config)

    assert trace.turn_count == 2
    assert len(trace.tool_calls_made) == 2
    assert trace.tool_calls_made[0]["name"] == "search"
    assert trace.tool_calls_made[1]["name"] == "lookup"
    assert trace.max_turns_hit is False


@pytest.mark.asyncio
async def test_runner_accumulates_usage():
    """Multi-turn execution accumulates token usage across all turns."""
    adapter = MockAdapter([
        AdapterTurnResult(
            content=None,
            tool_calls=[ToolCallResult(id="tc1", name="search", arguments={})],
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            raw_response={},
            finish_reason="tool_calls",
        ),
        AdapterTurnResult(
            content="Done.",
            tool_calls=[],
            usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
            raw_response={},
            finish_reason="stop",
        ),
    ])

    runner = ScenarioRunner(adapter)
    scenario = _make_scenario(
        tools=[ToolDef(name="search", description="Search", mock_response="data")],
    )
    config = _make_config()

    trace = await runner.run(scenario, config)

    # Usage should be accumulated, not just last turn
    assert trace.input_tokens == 300  # 100 + 200
    assert trace.output_tokens == 150  # 50 + 100
    assert trace.total_tokens == 450  # 150 + 300


@pytest.mark.asyncio
async def test_runner_scenario_hash_deterministic():
    """Same scenario produces the same hash."""
    adapter = MockAdapter([
        AdapterTurnResult(
            content="A", tool_calls=[], usage=TokenUsage(),
            raw_response={}, finish_reason="stop",
        ),
    ])
    adapter2 = MockAdapter([
        AdapterTurnResult(
            content="B", tool_calls=[], usage=TokenUsage(),
            raw_response={}, finish_reason="stop",
        ),
    ])

    scenario = _make_scenario(prompt="Deterministic test")
    config = _make_config()

    trace1 = await ScenarioRunner(adapter).run(scenario, config)
    trace2 = await ScenarioRunner(adapter2).run(scenario, config)

    assert trace1.scenario_hash == trace2.scenario_hash

    # Verify it matches expected SHA-256
    expected = hashlib.sha256(scenario.model_dump_json().encode()).hexdigest()
    assert trace1.scenario_hash == expected


@pytest.mark.asyncio
async def test_runner_cost_estimation():
    """Cost is estimated for known models."""
    adapter = MockAdapter([
        AdapterTurnResult(
            content="Hello",
            tool_calls=[],
            usage=TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500),
            raw_response={},
            finish_reason="stop",
        ),
    ])

    runner = ScenarioRunner(adapter)
    scenario = _make_scenario(model="gpt-4o")
    config = _make_config(model="gpt-4o")

    trace = await runner.run(scenario, config)

    assert trace.cost_usd is not None
    assert trace.cost_usd > 0
    # gpt-4o: $2.50/M input + $10.00/M output
    # 1000 input tokens: 1000/1M * 2.50 = 0.0025
    # 500 output tokens: 500/1M * 10.00 = 0.005
    # Total: 0.0075
    assert trace.cost_usd == 0.0075
