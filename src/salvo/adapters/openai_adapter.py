"""OpenAI adapter for the Salvo execution pipeline.

Converts unified Message/ToolDef types to OpenAI chat completion format
and extracts results into AdapterTurnResult.
"""

from __future__ import annotations

import json
from typing import Any

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)


class OpenAIAdapter(BaseAdapter):
    """Adapter for OpenAI chat completion API.

    Uses lazy-initialized AsyncOpenAI client that reads OPENAI_API_KEY
    from the environment automatically.
    """

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialize and return the AsyncOpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI()
        return self._client

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Messages to OpenAI chat format.

        Args:
            messages: List of unified Message objects.

        Returns:
            List of dicts in OpenAI chat completion message format.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                result.append({"role": "system", "content": msg.content})
            elif msg.role == "user":
                result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content,
                }
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(entry)
            elif msg.role == "tool_result":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
        return result

    def _convert_tools(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert unified tool definitions to OpenAI function format.

        Args:
            tools: List of tool definitions with name, description, parameters.

        Returns:
            List of dicts in OpenAI function tool format.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            }
            for tool in tools
        ]

    async def send_turn(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        config: AdapterConfig | None = None,
    ) -> AdapterTurnResult:
        """Send a single turn to the OpenAI API.

        Args:
            messages: Conversation history as unified Message objects.
            tools: Optional tool definitions.
            config: Optional adapter configuration.

        Returns:
            AdapterTurnResult with the model's response.
        """
        config = config or AdapterConfig(model="gpt-4o")
        client = self._get_client()

        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": self._convert_messages(messages),
        }

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        if config.temperature is not None:
            kwargs["temperature"] = config.temperature

        if config.max_tokens is not None:
            kwargs["max_tokens"] = config.max_tokens

        if config.seed is not None:
            kwargs["seed"] = config.seed

        # Pass through provider-specific extras
        kwargs.update(config.extras)

        response = await client.chat.completions.create(**kwargs)

        choice = response.choices[0]

        # Extract content
        content = choice.message.content

        # Extract tool calls
        tool_calls: list[ToolCallResult] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCallResult(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        # Extract usage
        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )

        return AdapterTurnResult(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            raw_response=response.model_dump(),
            finish_reason=choice.finish_reason,
        )

    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"
