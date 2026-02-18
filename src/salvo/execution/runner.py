"""ScenarioRunner: multi-turn conversation loop with mock tool injection.

Drives a scenario against an adapter, feeding mock tool responses back
into the conversation until the model produces a final answer (no tool
calls) or the max turns safety net is hit.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)
from salvo.execution.cost import estimate_cost
from salvo.execution.trace import RunTrace, TraceMessage
from salvo.models.scenario import Scenario


class ToolMockNotFoundError(Exception):
    """Raised when the model calls a tool with no mock_response defined.

    Attributes:
        tool_name: The name of the tool that was called.
        available_mocks: Set of tool names that have mock_response defined.
    """

    def __init__(self, tool_name: str, available_mocks: set[str]) -> None:
        self.tool_name = tool_name
        self.available_mocks = available_mocks
        super().__init__(
            f"Model called tool '{tool_name}' but no mock_response is defined. "
            f"Available mocks: {sorted(available_mocks) if available_mocks else 'none'}"
        )


def _message_to_trace(msg: Message) -> TraceMessage:
    """Convert a Message dataclass to a TraceMessage Pydantic model."""
    tool_calls_data: list[dict[str, Any]] | None = None
    if msg.tool_calls:
        tool_calls_data = [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in msg.tool_calls
        ]

    return TraceMessage(
        role=msg.role,
        content=msg.content,
        tool_calls=tool_calls_data,
        tool_call_id=msg.tool_call_id,
        tool_name=msg.tool_name,
    )


class ScenarioRunner:
    """Drives a multi-turn conversation loop for scenario execution.

    Takes an adapter and runs a scenario through it, feeding mock tool
    responses back into the conversation. Stops when the model produces
    a final answer (no tool calls) or the max turns safety net is hit.
    """

    def __init__(self, adapter: BaseAdapter) -> None:
        self.adapter = adapter

    async def run(self, scenario: Scenario, config: AdapterConfig) -> RunTrace:
        """Execute a scenario and return the full run trace.

        Args:
            scenario: The scenario to execute.
            config: Adapter configuration for this run.

        Returns:
            RunTrace with all messages, tool calls, usage, timing, and metadata.

        Raises:
            ToolMockNotFoundError: If the model calls a tool with no mock_response.
        """
        max_turns = scenario.max_turns

        # Build initial messages
        messages: list[Message] = []
        if scenario.system_prompt:
            messages.append(Message(role="system", content=scenario.system_prompt))
        messages.append(Message(role="user", content=scenario.prompt))

        # Build tool definitions from scenario
        tool_defs: list[dict[str, Any]] | None = None
        if scenario.tools:
            tool_defs = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.model_dump(),
                }
                for tool in scenario.tools
            ]

        # Build mock_responses map
        mock_responses: dict[str, str | dict[str, Any]] = {
            tool.name: tool.mock_response
            for tool in scenario.tools
            if tool.mock_response is not None
        }

        # Initialize tracking
        total_usage = TokenUsage()
        all_tool_calls: list[dict[str, Any]] = []
        start_time = time.perf_counter()
        turn_count = 0
        result: AdapterTurnResult | None = None

        # Multi-turn loop
        for _ in range(max_turns):
            turn_count += 1

            result = await self.adapter.send_turn(messages, tool_defs, config)

            # Accumulate token usage
            total_usage.input_tokens += result.usage.input_tokens
            total_usage.output_tokens += result.usage.output_tokens
            total_usage.total_tokens += result.usage.total_tokens

            # Append assistant message to conversation
            messages.append(
                Message(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls if result.tool_calls else None,
                )
            )

            # If no tool calls, model produced final answer
            if not result.tool_calls:
                break

            # Process ALL tool calls (handles parallel tool calls)
            for tc in result.tool_calls:
                if tc.name not in mock_responses:
                    raise ToolMockNotFoundError(
                        tool_name=tc.name,
                        available_mocks=set(mock_responses.keys()),
                    )

                # Serialize mock response
                mock = mock_responses[tc.name]
                if isinstance(mock, dict):
                    mock_content = json.dumps(mock)
                else:
                    mock_content = str(mock)

                # Append tool result message
                messages.append(
                    Message(
                        role="tool_result",
                        content=mock_content,
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                    )
                )

            # Record tool calls
            all_tool_calls.extend(
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in result.tool_calls
            )

        elapsed = time.perf_counter() - start_time

        # Determine if max turns was hit (still had pending tool calls)
        max_turns_hit = (
            turn_count >= max_turns
            and result is not None
            and bool(result.tool_calls)
        )

        # Compute scenario hash
        scenario_hash = hashlib.sha256(
            scenario.model_dump_json().encode()
        ).hexdigest()

        # Estimate cost
        cost_usd = estimate_cost(
            model=config.model,
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
        )

        # Build trace messages from conversation history
        trace_messages = [_message_to_trace(m) for m in messages]

        # Determine finish reason and final content
        finish_reason = result.finish_reason if result else "error"
        final_content = result.content if result else None

        return RunTrace(
            messages=trace_messages,
            tool_calls_made=all_tool_calls,
            turn_count=turn_count,
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
            total_tokens=total_usage.total_tokens,
            latency_seconds=elapsed,
            final_content=final_content,
            finish_reason=finish_reason,
            model=config.model,
            provider=self.adapter.provider_name(),
            timestamp=datetime.now(timezone.utc),
            scenario_hash=scenario_hash,
            cost_usd=cost_usd,
            extras_resolved=config.extras,
            max_turns_hit=max_turns_hit,
        )
