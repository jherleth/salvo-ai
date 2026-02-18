"""BaseAdapter ABC and unified message/result dataclasses.

All provider adapters (OpenAI, Anthropic, custom) subclass BaseAdapter
and implement send_turn(). The dataclasses here define the universal
types that flow through the entire execution pipeline.

These are plain dataclasses (not Pydantic) to avoid overhead in the
hot path of adapter calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallResult:
    """Result of a tool call extracted from the model response."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    """Token usage counts from a single adapter turn."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AdapterTurnResult:
    """Result of a single send_turn() call to a provider adapter.

    Captures the model's response content, any tool calls, token usage,
    the raw provider response (for debugging), and the finish reason.
    """

    content: str | None
    tool_calls: list[ToolCallResult]
    usage: TokenUsage
    raw_response: dict[str, Any]
    finish_reason: str


@dataclass
class Message:
    """A single message in the conversation history.

    Roles: system, user, assistant, tool_call, tool_result.
    """

    role: str
    content: str | None = None
    tool_calls: list[ToolCallResult] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass
class AdapterConfig:
    """Configuration passed to an adapter for a single run.

    Holds model name, generation parameters, and provider-specific
    extras (validated separately by execution/extras.py).
    """

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    seed: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """Abstract base class for all provider adapters.

    Subclasses must implement send_turn() which takes a conversation
    history, optional tool definitions, and adapter config, and returns
    an AdapterTurnResult.
    """

    @abstractmethod
    async def send_turn(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        config: AdapterConfig | None = None,
    ) -> AdapterTurnResult:
        """Send a single turn to the model and return the result.

        Args:
            messages: Conversation history as a list of Message objects.
            tools: Optional list of tool definitions in provider format.
            config: Optional adapter configuration for this turn.

        Returns:
            AdapterTurnResult with the model's response.
        """
        ...

    def provider_name(self) -> str:
        """Return the provider name for this adapter.

        Default implementation returns the class name.
        Subclasses may override for custom naming.
        """
        return type(self).__name__
