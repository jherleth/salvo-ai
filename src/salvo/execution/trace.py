"""Trace models for replay-ready run storage.

Pydantic models (not dataclasses) because traces are serialized to JSON
for persistence. Pydantic gives us model_dump/model_validate for free.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceMessage(BaseModel):
    """A single message in the conversation trace.

    Captures role, content, and optional tool call information
    for replay-ready storage.
    """

    role: str  # system, user, assistant, tool_result
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # Serialized ToolCallResult
    tool_call_id: str | None = None
    tool_name: str | None = None


class RunTrace(BaseModel):
    """Complete trace of a single scenario run.

    Contains all messages exchanged, tool calls made, token usage,
    timing, cost estimates, and provider metadata. Designed for
    lossless round-trip JSON serialization.
    """

    messages: list[TraceMessage]
    tool_calls_made: list[dict[str, Any]]  # All tool calls across turns
    turn_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_seconds: float
    final_content: str | None
    finish_reason: str
    model: str
    provider: str
    timestamp: datetime
    scenario_hash: str  # SHA-256 of resolved scenario
    cost_usd: float | None = None
    extras_resolved: dict[str, Any] = Field(default_factory=dict)
    max_turns_hit: bool = False  # True if terminated by safety net
