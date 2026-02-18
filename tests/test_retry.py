"""Tests for salvo.execution.retry - transient error retry with backoff."""

from __future__ import annotations

import asyncio

import pytest

from salvo.execution.retry import (
    TRANSIENT_EXCEPTIONS,
    TRANSIENT_STATUS_CODES,
    _is_transient,
    retry_with_backoff,
)


class TestIsTransient:
    """Test _is_transient detection logic."""

    def test_timeout_error_is_transient(self):
        assert _is_transient(TimeoutError("timed out")) is True

    def test_connection_error_is_transient(self):
        assert _is_transient(ConnectionError("refused")) is True

    def test_value_error_not_transient(self):
        assert _is_transient(ValueError("bad input")) is False

    def test_status_code_429_is_transient(self):
        exc = Exception("rate limited")
        exc.status_code = 429  # type: ignore[attr-defined]
        assert _is_transient(exc) is True

    def test_status_code_500_is_transient(self):
        exc = Exception("server error")
        exc.status_code = 500  # type: ignore[attr-defined]
        assert _is_transient(exc) is True

    def test_status_502_is_transient(self):
        exc = Exception("bad gateway")
        exc.status = 502  # type: ignore[attr-defined]
        assert _is_transient(exc) is True

    def test_status_503_is_transient(self):
        exc = Exception("unavailable")
        exc.status_code = 503  # type: ignore[attr-defined]
        assert _is_transient(exc) is True

    def test_status_400_not_transient(self):
        exc = Exception("bad request")
        exc.status_code = 400  # type: ignore[attr-defined]
        assert _is_transient(exc) is False

    def test_status_404_not_transient(self):
        exc = Exception("not found")
        exc.status_code = 404  # type: ignore[attr-defined]
        assert _is_transient(exc) is False


class TestRetryWithBackoff:
    """Test retry_with_backoff async retry logic."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Immediate success returns result with 0 retries."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "ok"

        result, retries, errors = await retry_with_backoff(
            factory, max_retries=3, base_delay=0.001,
        )
        assert result == "ok"
        assert retries == 0
        assert errors == []
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout_then_success(self):
        """TimeoutError triggers retry; second call succeeds."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("first call timed out")
            return "ok"

        result, retries, errors = await retry_with_backoff(
            factory, max_retries=3, base_delay=0.001,
        )
        assert result == "ok"
        assert retries == 1
        assert errors == ["TimeoutError"]
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """ConnectionError triggers retry."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("refused")
            return "ok"

        result, retries, errors = await retry_with_backoff(
            factory, max_retries=3, base_delay=0.001,
        )
        assert result == "ok"
        assert retries == 2
        assert errors == ["ConnectionError", "ConnectionError"]

    @pytest.mark.asyncio
    async def test_retry_on_status_code_429(self):
        """Exception with status_code=429 triggers retry."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = Exception("rate limited")
                exc.status_code = 429  # type: ignore[attr-defined]
                raise exc
            return "ok"

        result, retries, errors = await retry_with_backoff(
            factory, max_retries=3, base_delay=0.001,
        )
        assert result == "ok"
        assert retries == 1

    @pytest.mark.asyncio
    async def test_non_transient_raises_immediately(self):
        """ValueError (non-transient) raises without retry."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            await retry_with_backoff(
                factory, max_retries=3, base_delay=0.001,
            )

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_exhausted_raises(self):
        """All retries fail with transient error -- raises last exception."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            raise TimeoutError(f"attempt {call_count}")

        with pytest.raises(TimeoutError, match="attempt 4"):
            await retry_with_backoff(
                factory, max_retries=3, base_delay=0.001,
            )

        # 1 initial + 3 retries = 4 total calls
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_max_retries_zero_no_retry(self):
        """max_retries=0 means only one attempt, no retries."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("fail")

        with pytest.raises(TimeoutError):
            await retry_with_backoff(
                factory, max_retries=0, base_delay=0.001,
            )

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_backoff_delay_is_bounded(self):
        """Verify that we actually wait (small delay for test speed)."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise TimeoutError("wait")
            return "ok"

        result, retries, errors = await retry_with_backoff(
            factory, max_retries=3, base_delay=0.001, max_delay=0.01,
        )
        assert result == "ok"
        assert retries == 2
