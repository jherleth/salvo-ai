"""Anthropic adapter for the Salvo execution pipeline.

Converts unified Message/ToolDef types to Anthropic messages format
and extracts results into AdapterTurnResult.
"""

from __future__ import annotations

from typing import Any

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)


class AnthropicAdapter(BaseAdapter):
    """Adapter for Anthropic messages API.

    Uses lazy-initialized AsyncAnthropic client that reads ANTHROPIC_API_KEY
    from the environment automatically.
    """

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialize and return the AsyncAnthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic()
        return self._client

    def _extract_system(
        self, messages: list[Message]
    ) -> tuple[str | None, list[Message]]:
        """Extract system message from the message list.

        Anthropic uses a separate 'system' parameter instead of a system
        message in the messages array.

        Args:
            messages: List of unified Message objects.

        Returns:
            Tuple of (system_prompt or None, remaining messages).
        """
        system_prompt: str | None = None
        remaining: list[Message] = []
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                remaining.append(msg)
        return system_prompt, remaining

    def _convert_message(self, msg: Message) -> dict[str, Any]:
        """Convert a single unified Message to Anthropic format.

        Args:
            msg: A unified Message object (non-system).

        Returns:
            Dict in Anthropic message format.
        """
        if msg.role == "user":
            return {"role": "user", "content": msg.content}
        elif msg.role == "assistant":
            content: list[dict[str, Any]] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
            return {"role": "assistant", "content": content}
        elif msg.role == "tool_result":
            # Tool results are sent as user messages with tool_result content blocks
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                ],
            }
        else:
            # Fallback: treat as user message
            return {"role": "user", "content": msg.content}

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert a list of unified Messages to Anthropic format.

        Args:
            messages: List of unified Message objects (no system messages).

        Returns:
            List of dicts in Anthropic message format.
        """
        return [self._convert_message(msg) for msg in messages]

    def _convert_tools(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert unified tool definitions to Anthropic format.

        Anthropic uses 'input_schema' instead of 'parameters'.

        Args:
            tools: List of tool definitions with name, description, parameters.

        Returns:
            List of dicts in Anthropic tool format.
        """
        return [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {}),
            }
            for tool in tools
        ]

    async def send_turn(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        config: AdapterConfig | None = None,
    ) -> AdapterTurnResult:
        """Send a single turn to the Anthropic API.

        Args:
            messages: Conversation history as unified Message objects.
            tools: Optional tool definitions.
            config: Optional adapter configuration.

        Returns:
            AdapterTurnResult with the model's response.
        """
        config = config or AdapterConfig(model="claude-sonnet-4-5-20250514")
        client = self._get_client()

        # Extract system prompt (Anthropic uses separate param)
        system_prompt, remaining_messages = self._extract_system(messages)

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": self._convert_messages(remaining_messages),
            "max_tokens": config.max_tokens if config.max_tokens is not None else 4096,
        }

        if system_prompt is not None:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        if config.temperature is not None:
            kwargs["temperature"] = config.temperature

        # Pass through provider-specific extras
        kwargs.update(config.extras)

        response = await client.messages.create(**kwargs)

        # Extract content from text blocks
        content_parts: list[str] = []
        tool_calls: list[ToolCallResult] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallResult(
                        id=block.id,
                        name=block.name,
                        # block.input is already a dict, no json.loads needed
                        arguments=block.input,
                    )
                )

        content = "\n".join(content_parts) if content_parts else None

        # Extract usage
        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

        return AdapterTurnResult(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            raw_response=response.model_dump(),
            finish_reason=response.stop_reason,
        )

    def provider_name(self) -> str:
        """Return the provider name."""
        return "anthropic"
