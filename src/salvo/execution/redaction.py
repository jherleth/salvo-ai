"""Redaction and size limiting for trace storage safety.

Removes secret patterns (API keys, tokens, passwords) from trace
content and enforces size limits to prevent oversized trace files.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from salvo.execution.trace import RunTrace

# Regex patterns that match common secret formats.
# Applied to all trace message content before storage.
REDACTION_PATTERNS: list[str] = [
    r"(?i)bearer\s+[a-zA-Z0-9._-]+",  # Bearer tokens (before general auth pattern)
    r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key pattern
    r"(?i)(api[_-]?key|secret|password|token|authorization)\s*[:=]\s*\S+",
    r"(?i)cookie:\s*\S+",  # Cookie headers
    r"(?i)set-cookie:\s*\S+",  # Set-Cookie headers
    r"(?i)x-api-key:\s*\S+",  # X-API-Key headers
    r"sk-ant-[a-zA-Z0-9-]{20,}",  # Anthropic API key values
    r"ghp_[a-zA-Z0-9]{36}",  # GitHub PATs
    r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth tokens
]

# Compiled patterns for performance (compiled once at module load).
_COMPILED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p) for p in REDACTION_PATTERNS
]

REDACTED_PLACEHOLDER = "[REDACTED]"

# Size limits for trace storage.
MAX_MESSAGE_CONTENT_SIZE: int = 50_000  # 50KB per message
MAX_RAW_RESPONSE_SIZE: int = 100_000  # 100KB per raw response
MAX_TRACE_TOTAL_SIZE: int = 5_000_000  # 5MB total trace


def redact_content(content: str) -> str:
    """Replace secret patterns in content with [REDACTED].

    Applies all REDACTION_PATTERNS sequentially. Patterns that
    don't match are skipped (content passes through unchanged).

    Args:
        content: The string to redact.

    Returns:
        Content with matching secret patterns replaced.
    """
    for pattern in _COMPILED_PATTERNS:
        content = pattern.sub(REDACTED_PLACEHOLDER, content)
    return content


def truncate_content(content: str, max_size: int) -> str:
    """Truncate content to max_size characters, appending a notice if truncated.

    Args:
        content: The string to truncate.
        max_size: Maximum allowed length in characters.

    Returns:
        Original content if within limit, otherwise truncated with
        a '... [truncated]' suffix.
    """
    if len(content) <= max_size:
        return content
    return content[:max_size] + "... [truncated]"


def apply_trace_limits(trace: "RunTrace") -> "RunTrace":
    """Apply redaction and size limits to all trace messages.

    Iterates over trace.messages, applying redact_content and
    truncate_content to each message's content. Also truncates
    oversized tool_calls dicts.

    Args:
        trace: The RunTrace to sanitize.

    Returns:
        A new RunTrace with redacted and truncated content.
    """
    from salvo.execution.trace import RunTrace, TraceMessage

    sanitized_messages: list[TraceMessage] = []
    for msg in trace.messages:
        new_content = msg.content
        if new_content is not None:
            new_content = redact_content(new_content)
            new_content = truncate_content(new_content, MAX_MESSAGE_CONTENT_SIZE)

        new_tool_calls = msg.tool_calls
        if new_tool_calls is not None:
            # Truncate serialized tool_calls if too large
            serialized = json.dumps(new_tool_calls)
            if len(serialized) > MAX_RAW_RESPONSE_SIZE:
                new_tool_calls = [{"truncated": True, "original_count": len(new_tool_calls)}]

        sanitized_messages.append(
            TraceMessage(
                role=msg.role,
                content=new_content,
                tool_calls=new_tool_calls,
                tool_call_id=msg.tool_call_id,
                tool_name=msg.tool_name,
            )
        )

    return RunTrace(
        messages=sanitized_messages,
        tool_calls_made=trace.tool_calls_made,
        turn_count=trace.turn_count,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        total_tokens=trace.total_tokens,
        latency_seconds=trace.latency_seconds,
        final_content=trace.final_content,
        finish_reason=trace.finish_reason,
        model=trace.model,
        provider=trace.provider,
        timestamp=trace.timestamp,
        scenario_hash=trace.scenario_hash,
        cost_usd=trace.cost_usd,
        extras_resolved=trace.extras_resolved,
        max_turns_hit=trace.max_turns_hit,
    )
