"""Salvo adapters - provider adapter abstraction layer.

Re-exports the BaseAdapter ABC, all message/result dataclasses,
and the adapter registry function.
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
