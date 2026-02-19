"""Extended redaction pipeline for recorded traces.

Builds on the base execution redaction patterns, adding support for
user-defined custom patterns from salvo.yaml and a metadata_only
mode that strips message content while preserving structure.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from salvo.execution.redaction import REDACTED_PLACEHOLDER, _COMPILED_PATTERNS

if TYPE_CHECKING:
    from salvo.execution.trace import RunTrace


def build_redaction_pipeline(
    custom_patterns: list[str] | None = None,
) -> Callable[[str], str]:
    """Build a redaction function combining built-in and custom patterns.

    Built-in patterns are always included. Custom patterns extend
    (never replace) the built-in set. Custom patterns are compiled
    at build time for performance.

    Args:
        custom_patterns: Optional list of regex pattern strings to
            add on top of built-in patterns.

    Returns:
        A function that takes a string and returns it with all
        matching patterns replaced by [REDACTED].

    Raises:
        ValueError: If a custom pattern fails to compile.
    """
    all_patterns: list[re.Pattern[str]] = list(_COMPILED_PATTERNS)

    if custom_patterns:
        for pattern_str in custom_patterns:
            try:
                compiled = re.compile(pattern_str)
            except re.error as exc:
                raise ValueError(
                    f"Invalid custom redaction pattern {pattern_str!r}: {exc}"
                ) from exc
            all_patterns.append(compiled)

    def redact(content: str) -> str:
        for pattern in all_patterns:
            content = pattern.sub(REDACTED_PLACEHOLDER, content)
        return content

    return redact


def apply_custom_redaction(
    trace: "RunTrace",
    redact_fn: Callable[[str], str],
) -> "RunTrace":
    """Apply a custom redaction function to all trace message content.

    Follows the same message-by-message approach as apply_trace_limits()
    in execution/redaction.py, using RunTrace() constructor to match
    the existing pattern.

    Args:
        trace: The RunTrace to redact.
        redact_fn: A function that redacts a string.

    Returns:
        A new RunTrace with redacted content.
    """
    from salvo.execution.trace import RunTrace, TraceMessage

    redacted_messages: list[TraceMessage] = []
    for msg in trace.messages:
        new_content = msg.content
        if new_content is not None:
            new_content = redact_fn(new_content)

        redacted_messages.append(
            TraceMessage(
                role=msg.role,
                content=new_content,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id,
                tool_name=msg.tool_name,
            )
        )

    new_final = trace.final_content
    if new_final is not None:
        new_final = redact_fn(new_final)

    return RunTrace(
        messages=redacted_messages,
        tool_calls_made=trace.tool_calls_made,
        turn_count=trace.turn_count,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        total_tokens=trace.total_tokens,
        latency_seconds=trace.latency_seconds,
        final_content=new_final,
        finish_reason=trace.finish_reason,
        model=trace.model,
        provider=trace.provider,
        timestamp=trace.timestamp,
        scenario_hash=trace.scenario_hash,
        cost_usd=trace.cost_usd,
        extras_resolved=trace.extras_resolved,
        max_turns_hit=trace.max_turns_hit,
    )


def strip_content_for_metadata_only(trace: "RunTrace") -> "RunTrace":
    """Strip message content while preserving structure for metadata_only mode.

    For each message: sets content to '[CONTENT_EXCLUDED]' if content was
    present (else None), keeps tool_call id and name but replaces arguments
    with '[CONTENT_EXCLUDED]'. Sets final_content to None.

    Preserves: role, tool_call_id, tool_name, tokens, latency, etc.

    Args:
        trace: The RunTrace to strip.

    Returns:
        A new RunTrace with content stripped but structure preserved.
    """
    from salvo.execution.trace import RunTrace, TraceMessage

    stripped_messages: list[TraceMessage] = []
    for msg in trace.messages:
        new_content: str | None = None
        if msg.content is not None:
            new_content = "[CONTENT_EXCLUDED]"

        new_tool_calls = msg.tool_calls
        if new_tool_calls is not None:
            new_tool_calls = [
                {
                    **tc,
                    "arguments": "[CONTENT_EXCLUDED]"
                    if "arguments" in tc
                    else tc.get("arguments"),
                    "input": "[CONTENT_EXCLUDED]"
                    if "input" in tc
                    else tc.get("input"),
                }
                for tc in new_tool_calls
            ]
            # Clean up None keys that weren't in original
            new_tool_calls = [
                {k: v for k, v in tc.items() if v is not None}
                for tc in new_tool_calls
            ]

        stripped_messages.append(
            TraceMessage(
                role=msg.role,
                content=new_content,
                tool_calls=new_tool_calls,
                tool_call_id=msg.tool_call_id,
                tool_name=msg.tool_name,
            )
        )

    return RunTrace(
        messages=stripped_messages,
        tool_calls_made=trace.tool_calls_made,
        turn_count=trace.turn_count,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        total_tokens=trace.total_tokens,
        latency_seconds=trace.latency_seconds,
        final_content=None,
        finish_reason=trace.finish_reason,
        model=trace.model,
        provider=trace.provider,
        timestamp=trace.timestamp,
        scenario_hash=trace.scenario_hash,
        cost_usd=trace.cost_usd,
        extras_resolved=trace.extras_resolved,
        max_turns_hit=trace.max_turns_hit,
    )
