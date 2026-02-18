"""Tests for the adapter registry (get_adapter function)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import types

import pytest

from salvo.adapters.base import (
    AdapterTurnResult,
    BaseAdapter,
    TokenUsage,
)
from salvo.adapters.registry import get_adapter


# --- Test adapter for dotted-path tests ---


class _TestAdapter(BaseAdapter):
    """A valid test adapter for dotted-path loading tests."""

    async def send_turn(self, messages, tools=None, config=None):
        return AdapterTurnResult(
            content="test",
            tool_calls=[],
            usage=TokenUsage(),
            raw_response={},
            finish_reason="stop",
        )


class _NotAnAdapter:
    """Not a BaseAdapter subclass -- used to test type validation."""

    pass


# --- Registry tests ---


class TestGetAdapterBuiltin:
    """Test builtin adapter name resolution."""

    def test_get_adapter_builtin_openai_fails_without_sdk(self) -> None:
        """get_adapter('openai') should raise ImportError with install hint when SDK missing."""
        with patch("importlib.import_module", side_effect=ImportError("No module named 'openai'")):
            with pytest.raises(ImportError, match=r"pip install salvo-ai\[openai\]"):
                get_adapter("openai")

    def test_get_adapter_builtin_anthropic_fails_without_sdk(self) -> None:
        """get_adapter('anthropic') should raise ImportError with install hint when SDK missing."""
        with patch("importlib.import_module", side_effect=ImportError("No module named 'anthropic'")):
            with pytest.raises(ImportError, match=r"pip install salvo-ai\[anthropic\]"):
                get_adapter("anthropic")

    def test_get_adapter_builtin_openai_succeeds_with_sdk(self) -> None:
        """get_adapter('openai') returns an OpenAIAdapter when SDK is installed."""
        adapter = get_adapter("openai")
        assert isinstance(adapter, BaseAdapter)
        assert adapter.provider_name() == "openai"

    def test_get_adapter_builtin_anthropic_succeeds_with_sdk(self) -> None:
        """get_adapter('anthropic') returns an AnthropicAdapter when SDK is installed."""
        adapter = get_adapter("anthropic")
        assert isinstance(adapter, BaseAdapter)
        assert adapter.provider_name() == "anthropic"


class TestGetAdapterDottedPath:
    """Test custom dotted-path adapter loading."""

    def test_get_adapter_custom_dotted_path(self) -> None:
        """get_adapter with a dotted path loads the class and returns an instance."""
        # Create a mock module containing our test adapter
        mock_module = types.ModuleType("tests.test_adapters_registry")
        mock_module._TestAdapter = _TestAdapter  # type: ignore[attr-defined]

        with patch("importlib.import_module", return_value=mock_module):
            adapter = get_adapter("tests.test_adapters_registry._TestAdapter")

        assert isinstance(adapter, BaseAdapter)
        assert isinstance(adapter, _TestAdapter)

    def test_get_adapter_not_subclass_raises_type_error(self) -> None:
        """get_adapter raises TypeError if the loaded class is not a BaseAdapter subclass."""
        mock_module = types.ModuleType("tests.test_adapters_registry")
        mock_module._NotAnAdapter = _NotAnAdapter  # type: ignore[attr-defined]

        with patch("importlib.import_module", return_value=mock_module):
            with pytest.raises(TypeError, match="not a subclass of BaseAdapter"):
                get_adapter("tests.test_adapters_registry._NotAnAdapter")


class TestGetAdapterUnknown:
    """Test error handling for unknown adapter names."""

    def test_get_adapter_unknown_name(self) -> None:
        """get_adapter with an unknown name raises ValueError listing available adapters."""
        with pytest.raises(ValueError, match="Unknown adapter"):
            get_adapter("unknown")

    def test_get_adapter_unknown_name_lists_builtins(self) -> None:
        """Error message for unknown adapter includes available builtin names."""
        with pytest.raises(ValueError, match="openai") as exc_info:
            get_adapter("unknown")
        assert "anthropic" in str(exc_info.value)
