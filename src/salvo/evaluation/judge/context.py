"""Trace context builder for judge evaluation.

Assembles the context block that the judge LLM sees, including
the agent's final response, tool call summary, and optionally
the scenario system prompt and available tools.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from salvo.execution.trace import RunTrace
    from salvo.models.scenario import Scenario


def build_tool_call_summary(
    trace: RunTrace, max_arg_length: int = 100
) -> str:
    """Build a concise tool-call summary from the trace.

    Args:
        trace: The captured run trace.
        max_arg_length: Maximum character length for stringified arguments.

    Returns:
        Formatted tool call summary or "No tool calls were made."
    """
    if not trace.tool_calls_made:
        return "No tool calls were made."

    lines = []
    for i, tc in enumerate(trace.tool_calls_made, 1):
        name = tc.get("name", "unknown")
        args = tc.get("arguments", {})
        args_str = json.dumps(args, ensure_ascii=False)
        if len(args_str) > max_arg_length:
            args_str = args_str[:max_arg_length] + "..."
        lines.append(f"{i}. {name}({args_str})")

    return "\n".join(lines)


def build_context(
    trace: RunTrace,
    scenario: Scenario | None = None,
    include_system_prompt: bool = False,
) -> str:
    """Build the context block the judge sees.

    Always includes the agent's final response and tool call summary.
    Optionally includes the scenario system prompt and available tools
    when include_system_prompt is True and a scenario is provided.

    Args:
        trace: The captured run trace.
        scenario: Optional scenario for system prompt / tool defs.
        include_system_prompt: Whether to include system prompt sections.

    Returns:
        Formatted context string with markdown sections.
    """
    sections = []

    # Optionally include system prompt and tools
    if include_system_prompt and scenario is not None:
        sp = scenario.system_prompt or ""
        if len(sp) > 2000:
            sp = sp[:2000] + "..."
        sections.append(f"## Scenario System Prompt\n\n{sp}")

        if scenario.tools:
            tool_lines = []
            for t in scenario.tools:
                tool_lines.append(f"- **{t.name}**: {t.description}")
            sections.append("## Available Tools\n\n" + "\n".join(tool_lines))

    # Always include final response
    final = trace.final_content if trace.final_content else "(empty)"
    sections.append(f"## Agent's Final Response\n\n{final}")

    # Always include tool call summary
    summary = build_tool_call_summary(trace)
    sections.append(f"## Tool Calls Made\n\n{summary}")

    return "\n\n".join(sections)
