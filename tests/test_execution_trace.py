"""Tests for trace models (RunTrace, TraceMessage)."""

from datetime import datetime, timezone

from salvo.execution.trace import RunTrace, TraceMessage


def test_trace_message_serialization():
    """TraceMessage round-trips through JSON serialization."""
    msg = TraceMessage(
        role="assistant",
        content="Hello",
        tool_calls=[{"id": "tc1", "name": "search", "arguments": {"q": "test"}}],
    )
    data = msg.model_dump()
    assert data["role"] == "assistant"
    assert data["content"] == "Hello"
    assert len(data["tool_calls"]) == 1
    assert data["tool_calls"][0]["name"] == "search"

    # Round-trip via JSON
    json_str = msg.model_dump_json()
    restored = TraceMessage.model_validate_json(json_str)
    assert restored.role == msg.role
    assert restored.content == msg.content
    assert restored.tool_calls == msg.tool_calls


def test_run_trace_round_trip():
    """RunTrace round-trips through model_dump_json + model_validate_json."""
    now = datetime.now(timezone.utc)
    trace = RunTrace(
        messages=[
            TraceMessage(role="user", content="Hello"),
            TraceMessage(role="assistant", content="Hi there"),
        ],
        tool_calls_made=[],
        turn_count=1,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        latency_seconds=0.5,
        final_content="Hi there",
        finish_reason="stop",
        model="gpt-4o",
        provider="OpenAIAdapter",
        timestamp=now,
        scenario_hash="abc123",
        cost_usd=0.000035,
    )

    json_str = trace.model_dump_json()
    restored = RunTrace.model_validate_json(json_str)

    assert restored.turn_count == 1
    assert restored.input_tokens == 10
    assert restored.output_tokens == 5
    assert restored.total_tokens == 15
    assert restored.model == "gpt-4o"
    assert restored.cost_usd == 0.000035
    assert len(restored.messages) == 2
    assert restored.messages[0].role == "user"
    assert restored.messages[1].content == "Hi there"
    assert restored.scenario_hash == "abc123"


def test_run_trace_defaults():
    """RunTrace has sensible defaults for optional fields."""
    now = datetime.now(timezone.utc)
    trace = RunTrace(
        messages=[],
        tool_calls_made=[],
        turn_count=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        latency_seconds=0.0,
        final_content=None,
        finish_reason="stop",
        model="gpt-4o",
        provider="OpenAIAdapter",
        timestamp=now,
        scenario_hash="def456",
    )

    assert trace.cost_usd is None
    assert trace.extras_resolved == {}
    assert trace.max_turns_hit is False
    assert trace.final_content is None
