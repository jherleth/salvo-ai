"""Salvo adapters - provider adapter abstraction layer.

Re-exports the BaseAdapter ABC, all message/result dataclasses,
the adapter registry function, and concrete adapter implementations
(when their SDK dependencies are installed).
"""

from salvo.adapters.base import (
    AdapterConfig,
    AdapterTurnResult,
    BaseAdapter,
    Message,
    TokenUsage,
    ToolCallResult,
)
from salvo.adapters.registry import get_adapter

__all__ = [
    "AdapterConfig",
    "AdapterTurnResult",
    "BaseAdapter",
    "Message",
    "TokenUsage",
    "ToolCallResult",
    "get_adapter",
]

# Optional re-exports: only available when provider SDKs are installed
try:
    from salvo.adapters.openai_adapter import OpenAIAdapter

    __all__.append("OpenAIAdapter")
except ImportError:
    pass

try:
    from salvo.adapters.anthropic_adapter import AnthropicAdapter

    __all__.append("AnthropicAdapter")
except ImportError:
    pass
