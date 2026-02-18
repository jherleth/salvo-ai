"""Tests for salvo.adapters.openai_adapter - OpenAI adapter implementation.

Uses unittest.mock to mock the OpenAI SDK client, so tests run
without API keys or network access.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salvo.adapters.base import (
    AdapterConfig,
    Message,
    ToolCallResult,
)
from salvo.adapters.openai_adapter import OpenAIAdapter


class TestOpenAIConvertMessages:
    """Test message format conversion to OpenAI chat format."""

    def test_openai_convert_messages_system(self):
        """System message converts to role=system."""
        adapter = OpenAIAdapter()
        messages = [Message(role="system", content="You are helpful.")]
        result = adapter._convert_messages(messages)
        assert result == [{"role": "system", "content": "You are helpful."}]

    def test_openai_convert_messages_user(self):
        """User message converts to role=user."""
        adapter = OpenAIAdapter()
        messages = [Message(role="user", content="Hello")]
        result = adapter._convert_messages(messages)
        assert result == [{"role": "user", "content": "Hello"}]

    def test_openai_convert_messages_assistant(self):
        """Assistant message converts to role=assistant with content."""
        adapter = OpenAIAdapter()
        messages = [Message(role="assistant", content="Hi there")]
        result = adapter._convert_messages(messages)
        assert result == [{"role": "assistant", "content": "Hi there"}]

    def test_openai_convert_messages_assistant_with_tool_calls(self):
        """Assistant message with tool_calls includes tool_calls array."""
        adapter = OpenAIAdapter()
        messages = [
            Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCallResult(
                        id="call_123",
                        name="file_read",
                        arguments={"path": "/tmp/test.py"},
                    )
                ],
            )
        ]
        result = adapter._convert_messages(messages)
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "assistant"
        assert msg["content"] is None
        assert len(msg["tool_calls"]) == 1
        tc = msg["tool_calls"][0]
        assert tc["id"] == "call_123"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "file_read"
        assert json.loads(tc["function"]["arguments"]) == {"path": "/tmp/test.py"}

    def test_openai_convert_messages_tool_result(self):
        """Tool result converts to role=tool with tool_call_id."""
        adapter = OpenAIAdapter()
        messages = [
            Message(
                role="tool_result",
                content="file contents here",
                tool_call_id="call_123",
            )
        ]
        result = adapter._convert_messages(messages)
        assert result == [
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "content": "file contents here",
            }
        ]


class TestOpenAIConvertTools:
    """Test tool definition conversion to OpenAI format."""

    def test_openai_convert_tools(self):
        """Tool defs convert to OpenAI function format."""
        adapter = OpenAIAdapter()
        tools = [
            {
                "name": "file_read",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            }
        ]
        result = adapter._convert_tools(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "file_read"
        assert result[0]["function"]["description"] == "Read a file"
        assert result[0]["function"]["parameters"]["type"] == "object"


class TestOpenAISendTurn:
    """Test send_turn with mocked OpenAI client."""

    def _mock_response(
        self,
        content: str | None = "Hello!",
        tool_calls: list | None = None,
        finish_reason: str = "stop",
        prompt_tokens: int = 10,
        completion_tokens: int = 5,
        total_tokens: int = 15,
    ) -> MagicMock:
        """Create a realistic mock OpenAI ChatCompletion response."""
        mock_msg = MagicMock()
        mock_msg.content = content
        mock_msg.tool_calls = tool_calls

        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_choice.finish_reason = finish_reason

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = prompt_tokens
        mock_usage.completion_tokens = completion_tokens
        mock_usage.total_tokens = total_tokens

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model_dump.return_value = {"id": "chatcmpl-123", "object": "chat.completion"}

        return mock_response

    def _mock_tool_call(
        self,
        tc_id: str = "call_abc",
        name: str = "file_read",
        arguments: dict | None = None,
    ) -> MagicMock:
        """Create a mock OpenAI tool call object."""
        if arguments is None:
            arguments = {"path": "/tmp/test.py"}
        mock_tc = MagicMock()
        mock_tc.id = tc_id
        mock_tc.function.name = name
        mock_tc.function.arguments = json.dumps(arguments)
        return mock_tc

    @pytest.mark.asyncio
    async def test_openai_send_turn_text_response(self):
        """Text response extracts content, empty tool_calls, and usage."""
        adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._mock_response(content="Hello!")
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="Hi")],
            config=AdapterConfig(model="gpt-4o"),
        )

        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5
        assert result.usage.total_tokens == 15
        assert result.raw_response == {"id": "chatcmpl-123", "object": "chat.completion"}

    @pytest.mark.asyncio
    async def test_openai_send_turn_tool_call_response(self):
        """Tool call response extracts tool calls with parsed arguments."""
        adapter = OpenAIAdapter()
        mock_tc = self._mock_tool_call(
            tc_id="call_xyz",
            name="file_read",
            arguments={"path": "/tmp/test.py"},
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._mock_response(
                content=None,
                tool_calls=[mock_tc],
                finish_reason="tool_calls",
            )
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="Read the file")],
            config=AdapterConfig(model="gpt-4o"),
        )

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_xyz"
        assert result.tool_calls[0].name == "file_read"
        assert result.tool_calls[0].arguments == {"path": "/tmp/test.py"}
        assert result.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_openai_send_turn_usage_extraction(self):
        """Usage fields are correctly mapped from OpenAI response."""
        adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._mock_response(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(model="gpt-4o"),
        )

        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 50
        assert result.usage.total_tokens == 150

    @pytest.mark.asyncio
    async def test_openai_send_turn_extras_passed_through(self):
        """Extras from config are passed through to the API call."""
        adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(
                model="gpt-4o",
                extras={"top_p": 0.9, "presence_penalty": 0.5},
            ),
        )

        # Verify extras were included in the API call kwargs
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["top_p"] == 0.9
        assert call_kwargs["presence_penalty"] == 0.5

    @pytest.mark.asyncio
    async def test_openai_send_turn_temperature_and_seed(self):
        """Temperature and seed from config are passed to the API call."""
        adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(model="gpt-4o", temperature=0.3, seed=42),
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["seed"] == 42

    def test_openai_provider_name(self):
        """provider_name() returns 'openai'."""
        adapter = OpenAIAdapter()
        assert adapter.provider_name() == "openai"

    def test_openai_lazy_client_init(self):
        """Client is not created until first send_turn."""
        adapter = OpenAIAdapter()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_openai_send_turn_with_tools(self):
        """Tools are converted and passed to the API call."""
        adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        tools = [
            {
                "name": "file_read",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

        await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            tools=tools,
            config=AdapterConfig(model="gpt-4o"),
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "file_read"
