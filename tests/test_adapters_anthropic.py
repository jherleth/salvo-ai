"""Tests for salvo.adapters.anthropic_adapter - Anthropic adapter implementation.

Uses unittest.mock to mock the Anthropic SDK client, so tests run
without API keys or network access.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from salvo.adapters.base import (
    AdapterConfig,
    Message,
    ToolCallResult,
)
from salvo.adapters.anthropic_adapter import AnthropicAdapter


class TestAnthropicConvertMessages:
    """Test message format conversion to Anthropic format."""

    def test_anthropic_convert_messages_extracts_system(self):
        """System message is extracted and removed from messages list."""
        adapter = AnthropicAdapter()
        messages = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
        ]
        system, remaining = adapter._extract_system(messages)
        assert system == "You are helpful."
        assert len(remaining) == 1
        assert remaining[0].role == "user"

    def test_anthropic_convert_messages_no_system(self):
        """When no system message, returns None and all messages."""
        adapter = AnthropicAdapter()
        messages = [Message(role="user", content="Hello")]
        system, remaining = adapter._extract_system(messages)
        assert system is None
        assert len(remaining) == 1

    def test_anthropic_convert_messages_user(self):
        """User message converts to Anthropic user format."""
        adapter = AnthropicAdapter()
        msg = Message(role="user", content="Hello")
        result = adapter._convert_message(msg)
        assert result == {"role": "user", "content": "Hello"}

    def test_anthropic_convert_messages_assistant_with_text(self):
        """Assistant text message converts to content blocks."""
        adapter = AnthropicAdapter()
        msg = Message(role="assistant", content="Hi there")
        result = adapter._convert_message(msg)
        assert result["role"] == "assistant"
        assert result["content"] == [{"type": "text", "text": "Hi there"}]

    def test_anthropic_convert_messages_assistant_with_tool_use(self):
        """Assistant message with tool_calls includes tool_use content blocks."""
        adapter = AnthropicAdapter()
        msg = Message(
            role="assistant",
            content="Let me read that file.",
            tool_calls=[
                ToolCallResult(
                    id="toolu_123",
                    name="file_read",
                    arguments={"path": "/tmp/test.py"},
                )
            ],
        )
        result = adapter._convert_message(msg)
        assert result["role"] == "assistant"
        assert len(result["content"]) == 2
        assert result["content"][0] == {"type": "text", "text": "Let me read that file."}
        assert result["content"][1] == {
            "type": "tool_use",
            "id": "toolu_123",
            "name": "file_read",
            "input": {"path": "/tmp/test.py"},
        }

    def test_anthropic_convert_messages_tool_result(self):
        """Tool result converts to user message with tool_result content block."""
        adapter = AnthropicAdapter()
        msg = Message(
            role="tool_result",
            content="file contents here",
            tool_call_id="toolu_123",
        )
        result = adapter._convert_message(msg)
        assert result["role"] == "user"
        assert result["content"] == [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "file contents here",
            }
        ]


class TestAnthropicConvertTools:
    """Test tool definition conversion to Anthropic format."""

    def test_anthropic_convert_tools(self):
        """Tool defs convert to Anthropic format with input_schema."""
        adapter = AnthropicAdapter()
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
        assert result[0]["name"] == "file_read"
        assert result[0]["description"] == "Read a file"
        # Anthropic uses input_schema, NOT parameters
        assert "input_schema" in result[0]
        assert "parameters" not in result[0]
        assert result[0]["input_schema"]["type"] == "object"


class TestAnthropicSendTurn:
    """Test send_turn with mocked Anthropic client."""

    def _mock_text_block(self, text: str = "Hello!") -> MagicMock:
        """Create a mock Anthropic text content block."""
        block = MagicMock()
        block.type = "text"
        block.text = text
        return block

    def _mock_tool_use_block(
        self,
        block_id: str = "toolu_abc",
        name: str = "file_read",
        input_data: dict | None = None,
    ) -> MagicMock:
        """Create a mock Anthropic tool_use content block."""
        if input_data is None:
            input_data = {"path": "/tmp/test.py"}
        block = MagicMock()
        block.type = "tool_use"
        block.id = block_id
        block.name = name
        block.input = input_data
        return block

    def _mock_response(
        self,
        content: list | None = None,
        stop_reason: str = "end_turn",
        input_tokens: int = 10,
        output_tokens: int = 5,
    ) -> MagicMock:
        """Create a realistic mock Anthropic Message response."""
        if content is None:
            content = [self._mock_text_block("Hello!")]

        mock_usage = MagicMock()
        mock_usage.input_tokens = input_tokens
        mock_usage.output_tokens = output_tokens

        mock_response = MagicMock()
        mock_response.content = content
        mock_response.stop_reason = stop_reason
        mock_response.usage = mock_usage
        mock_response.model_dump.return_value = {
            "id": "msg_123",
            "type": "message",
        }

        return mock_response

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_text_response(self):
        """Text response extracts content from text blocks."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response(
                content=[self._mock_text_block("Hello!")]
            )
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="Hi")],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_tool_use_response(self):
        """Tool use response extracts tool calls (arguments already dict)."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response(
                content=[
                    self._mock_tool_use_block(
                        block_id="toolu_xyz",
                        name="file_read",
                        input_data={"path": "/tmp/test.py"},
                    )
                ],
                stop_reason="tool_use",
            )
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="Read the file")],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_xyz"
        assert result.tool_calls[0].name == "file_read"
        assert result.tool_calls[0].arguments == {"path": "/tmp/test.py"}
        assert result.finish_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_usage_extraction(self):
        """Usage fields are correctly mapped from Anthropic response."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response(
                input_tokens=100,
                output_tokens=50,
            )
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 50
        assert result.usage.total_tokens == 150

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_max_tokens_default(self):
        """Default max_tokens is 4096 when config.max_tokens is None."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_max_tokens_custom(self):
        """Custom max_tokens overrides the default."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514", max_tokens=2048),
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_extras_passed_through(self):
        """Extras from config are passed through to the API call."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        await adapter.send_turn(
            messages=[Message(role="user", content="test")],
            config=AdapterConfig(
                model="claude-sonnet-4-5-20250514",
                extras={"top_k": 40},
            ),
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["top_k"] == 40

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_system_as_param(self):
        """System message is passed as separate 'system' param, not in messages."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response()
        )
        adapter._client = mock_client

        await adapter.send_turn(
            messages=[
                Message(role="system", content="You are helpful."),
                Message(role="user", content="Hello"),
            ],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are helpful."
        # System should not appear in messages
        for msg in call_kwargs["messages"]:
            assert msg["role"] != "system"

    def test_anthropic_provider_name(self):
        """provider_name() returns 'anthropic'."""
        adapter = AnthropicAdapter()
        assert adapter.provider_name() == "anthropic"

    def test_anthropic_lazy_client_init(self):
        """Client is not created until first send_turn."""
        adapter = AnthropicAdapter()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_with_tools(self):
        """Tools are converted and passed to the API call."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
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
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["name"] == "file_read"
        assert "input_schema" in call_kwargs["tools"][0]
        assert "parameters" not in call_kwargs["tools"][0]

    @pytest.mark.asyncio
    async def test_anthropic_send_turn_mixed_content(self):
        """Response with both text and tool_use blocks is correctly parsed."""
        adapter = AnthropicAdapter()
        mock_client = MagicMock()

        text_block = self._mock_text_block("Let me read that file.")
        tool_block = self._mock_tool_use_block(
            block_id="toolu_mixed",
            name="file_read",
            input_data={"path": "/tmp/test.py"},
        )

        mock_client.messages.create = AsyncMock(
            return_value=self._mock_response(
                content=[text_block, tool_block],
                stop_reason="tool_use",
            )
        )
        adapter._client = mock_client

        result = await adapter.send_turn(
            messages=[Message(role="user", content="Read the file")],
            config=AdapterConfig(model="claude-sonnet-4-5-20250514"),
        )

        assert result.content == "Let me read that file."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_mixed"
        assert result.finish_reason == "tool_use"
