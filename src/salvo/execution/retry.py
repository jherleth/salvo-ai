"""Transient error retry with exponential backoff and jitter.

Hand-rolled retry logic (~20 lines core) to avoid adding tenacity
as a dependency. Handles timeout, connection, and HTTP status-code
errors that are likely transient.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any

# Exception types considered transient (network-level issues)
TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (TimeoutError, ConnectionError)

# HTTP status codes considered transient (rate-limit, server errors)
TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503})


def _is_transient(exc: Exception) -> bool:
    """Check if an exception represents a transient error.

    Matches against known transient exception types, then checks
    for HTTP status code attributes commonly set by SDK exceptions.
    """
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True

    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is not None and status in TRANSIENT_STATUS_CODES:
        return True

    return False


async def retry_with_backoff(
    coro_factory: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> tuple[Any, int, list[str]]:
    """Execute a coroutine with retry on transient errors.

    Uses exponential backoff with full jitter to avoid thundering herd.
    Returns (result, retries_used, error_types) on success.
    Raises the exception on non-transient errors or when retries are exhausted.

    Args:
        coro_factory: Callable that creates a new awaitable each call.
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1).
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum backoff delay cap in seconds.

    Returns:
        Tuple of (result, retries_used, list of transient error type names).

    Raises:
        Exception: The last exception if all retries exhausted or non-transient.
    """
    retries_used = 0
    error_types: list[str] = []

    for attempt in range(max_retries + 1):
        try:
            result = await coro_factory()
            return (result, retries_used, error_types)
        except Exception as exc:
            is_last = attempt == max_retries
            if not _is_transient(exc) or is_last:
                raise

            retries_used += 1
            error_types.append(type(exc).__name__)
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay)  # noqa: S311
            await asyncio.sleep(jitter)

    # Unreachable, but satisfies type checker
    raise RuntimeError("Retry loop exited unexpectedly")  # pragma: no cover
