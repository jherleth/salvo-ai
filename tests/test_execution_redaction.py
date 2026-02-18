"""Tests for redaction and size limiting utilities."""

from datetime import datetime, timezone

from salvo.execution.redaction import (
    MAX_MESSAGE_CONTENT_SIZE,
    apply_trace_limits,
    redact_content,
    truncate_content,
)
from salvo.execution.trace import RunTrace, TraceMessage


def test_redact_api_key_pattern():
    """Redacts api_key=... patterns."""
    text = "config: api_key=sk-abc123secret"
    result = redact_content(text)
    assert "sk-abc123secret" not in result
    assert "[REDACTED]" in result


def test_redact_openai_key_pattern():
    """Redacts sk-... OpenAI key patterns."""
    text = "Using key sk-abcdefghijklmnopqrstuvwxyz for auth"
    result = redact_content(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in result
    assert "[REDACTED]" in result


def test_redact_bearer_token():
    """Redacts Bearer token patterns."""
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
    result = redact_content(text)
    assert "eyJhbGciOiJIUzI1NiJ9" not in result
    assert "[REDACTED]" in result


def test_redact_no_match_passthrough():
    """Content without secret patterns passes through unchanged."""
    text = "This is a normal message with no secrets."
    result = redact_content(text)
    assert result == text


def test_truncate_within_limit():
    """Content within limit is returned unchanged."""
    text = "short content"
    result = truncate_content(text, 100)
    assert result == text


def test_truncate_exceeds_limit():
    """Content exceeding limit is truncated with notice."""
    text = "a" * 200
    result = truncate_content(text, 100)
    assert len(result) > 100  # includes the suffix
    assert result.startswith("a" * 100)
    assert result.endswith("... [truncated]")


def test_apply_trace_limits_redacts_messages():
    """apply_trace_limits redacts secrets in message content."""
    now = datetime.now(timezone.utc)
    trace = RunTrace(
        messages=[
            TraceMessage(role="user", content="Hello"),
            TraceMessage(
                role="assistant",
                content="The api_key=super_secret_value is set",
            ),
            TraceMessage(
                role="tool_result",
                content="Result with Bearer my.jwt.token123 inside",
                tool_call_id="tc1",
                tool_name="lookup",
            ),
        ],
        tool_calls_made=[],
        turn_count=1,
        input_tokens=50,
        output_tokens=20,
        total_tokens=70,
        latency_seconds=1.0,
        final_content="The api_key=super_secret_value is set",
        finish_reason="stop",
        model="gpt-4o",
        provider="OpenAIAdapter",
        timestamp=now,
        scenario_hash="abc",
    )

    sanitized = apply_trace_limits(trace)

    # User message passes through (no secrets)
    assert sanitized.messages[0].content == "Hello"

    # Assistant message has api_key redacted
    assert "super_secret_value" not in sanitized.messages[1].content
    assert "[REDACTED]" in sanitized.messages[1].content

    # Tool result has Bearer token redacted
    assert "my.jwt.token123" not in sanitized.messages[2].content
    assert "[REDACTED]" in sanitized.messages[2].content

    # Metadata preserved
    assert sanitized.turn_count == 1
    assert sanitized.model == "gpt-4o"
    assert sanitized.scenario_hash == "abc"
