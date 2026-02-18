"""Tests for BaseAdapter ABC and unified message/result dataclasses."""

from __future__ import annotations

import pytest

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)


# --- BaseAdapter ABC tests ---


class TestBaseAdapterABC:
    """Test that BaseAdapter enforces the abstract interface contract."""

    def test_cannot_instantiate_base_adapter(self) -> None:
        """BaseAdapter itself cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseAdapter()  # type: ignore[abstract]

    def test_subclass_with_send_turn_instantiates(self) -> None:
        """A subclass that implements send_turn() can be created."""

        class GoodAdapter(BaseAdapter):
            async def send_turn(self, messages, tools=None, config=None):
                return AdapterTurnResult(
                    content="ok",
                    tool_calls=[],
                    usage=TokenUsage(),
                    raw_response={},
                    finish_reason="stop",
                )

        adapter = GoodAdapter()
        assert adapter is not None

    def test_subclass_without_send_turn_raises(self) -> None:
        """A subclass missing send_turn() cannot be instantiated."""

        class BadAdapter(BaseAdapter):
            pass

        with pytest.raises(TypeError):
            BadAdapter()  # type: ignore[abstract]

    def test_provider_name_default(self) -> None:
        """provider_name() returns the class name by default."""

        class MyCustomAdapter(BaseAdapter):
            async def send_turn(self, messages, tools=None, config=None):
                return AdapterTurnResult(
                    content="ok",
                    tool_calls=[],
                    usage=TokenUsage(),
                    raw_response={},
                    finish_reason="stop",
                )

        adapter = MyCustomAdapter()
        assert adapter.provider_name() == "MyCustomAdapter"


# --- Dataclass tests ---


class TestToolCallResult:
    """Test ToolCallResult dataclass."""

    def test_create_tool_call_result(self) -> None:
        tc = ToolCallResult(id="tc_1", name="get_weather", arguments={"city": "NYC"})
        assert tc.id == "tc_1"
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "NYC"}


class TestTokenUsage:
    """Test TokenUsage dataclass defaults."""

    def test_defaults_to_zero(self) -> None:
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_custom_values(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150


class TestAdapterTurnResult:
    """Test AdapterTurnResult dataclass."""

    def test_create_with_content(self) -> None:
        result = AdapterTurnResult(
            content="Hello!",
            tool_calls=[],
            usage=TokenUsage(),
            raw_response={"id": "123"},
            finish_reason="stop",
        )
        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"

    def test_create_with_tool_calls(self) -> None:
        tc = ToolCallResult(id="tc_1", name="search", arguments={"q": "test"})
        result = AdapterTurnResult(
            content=None,
            tool_calls=[tc],
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            raw_response={},
            finish_reason="tool_calls",
        )
        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search"


class TestMessage:
    """Test Message dataclass."""

    def test_user_message(self) -> None:
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None
        assert msg.tool_name is None

    def test_assistant_message_with_tool_calls(self) -> None:
        tc = ToolCallResult(id="tc_1", name="search", arguments={"q": "test"})
        msg = Message(role="assistant", content=None, tool_calls=[tc])
        assert msg.role == "assistant"
        assert msg.content is None
        assert len(msg.tool_calls) == 1

    def test_tool_result_message(self) -> None:
        msg = Message(
            role="tool_result",
            content='{"result": "sunny"}',
            tool_call_id="tc_1",
            tool_name="get_weather",
        )
        assert msg.role == "tool_result"
        assert msg.tool_call_id == "tc_1"
        assert msg.tool_name == "get_weather"


class TestAdapterConfig:
    """Test AdapterConfig dataclass."""

    def test_minimal_config(self) -> None:
        config = AdapterConfig(model="gpt-4o")
        assert config.model == "gpt-4o"
        assert config.temperature is None
        assert config.max_tokens is None
        assert config.seed is None
        assert config.extras == {}

    def test_full_config(self) -> None:
        config = AdapterConfig(
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            seed=42,
            extras={"response_format": {"type": "json_object"}},
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.seed == 42
        assert config.extras["response_format"]["type"] == "json_object"
