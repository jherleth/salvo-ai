"""Tests for extras validation with security guardrails."""

from __future__ import annotations

import pytest

from salvo.execution.extras import validate_extras


class TestValidateExtrasPassthrough:
    """Test that valid extras pass through unchanged."""

    def test_validate_extras_passthrough(self) -> None:
        """Valid extras dict is returned as-is."""
        extras = {"response_format": {"type": "text"}}
        result = validate_extras(extras)
        assert result == extras

    def test_validate_extras_empty_dict(self) -> None:
        """Empty dict is valid and returns empty dict."""
        result = validate_extras({})
        assert result == {}


class TestValidateExtrasBlockedKeys:
    """Test that secret-like keys are rejected."""

    def test_validate_extras_blocks_api_key(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            validate_extras({"api_key": "sk-xxx"})

    def test_validate_extras_blocks_token(self) -> None:
        with pytest.raises(ValueError, match="token"):
            validate_extras({"token": "abc"})

    def test_validate_extras_blocks_password(self) -> None:
        with pytest.raises(ValueError, match="password"):
            validate_extras({"password": "abc"})

    def test_validate_extras_blocks_authorization(self) -> None:
        with pytest.raises(ValueError, match="authorization"):
            validate_extras({"authorization": "Bearer xxx"})

    def test_validate_extras_blocks_api_secret(self) -> None:
        with pytest.raises(ValueError, match="api_secret"):
            validate_extras({"api_secret": "xxx"})

    def test_validate_extras_blocks_secret(self) -> None:
        with pytest.raises(ValueError, match="secret"):
            validate_extras({"secret": "xxx"})

    def test_validate_extras_blocks_secret_key(self) -> None:
        with pytest.raises(ValueError, match="secret_key"):
            validate_extras({"secret_key": "xxx"})

    def test_validate_extras_blocks_access_token(self) -> None:
        with pytest.raises(ValueError, match="access_token"):
            validate_extras({"access_token": "xxx"})

    def test_validate_extras_blocks_refresh_token(self) -> None:
        with pytest.raises(ValueError, match="refresh_token"):
            validate_extras({"refresh_token": "xxx"})

    def test_validate_extras_case_insensitive(self) -> None:
        """Blocklist matching is case-insensitive."""
        with pytest.raises(ValueError, match="(?i)api_key"):
            validate_extras({"API_KEY": "sk-xxx"})

        with pytest.raises(ValueError, match="(?i)token"):
            validate_extras({"Token": "abc"})

        with pytest.raises(ValueError, match="(?i)password"):
            validate_extras({"PASSWORD": "abc"})


class TestValidateExtrasLimits:
    """Test key count and size limits."""

    def test_validate_extras_too_many_keys(self) -> None:
        """More than 10 keys should raise ValueError."""
        extras = {f"key_{i}": "value" for i in range(11)}
        with pytest.raises(ValueError, match="10"):
            validate_extras(extras)

    def test_validate_extras_exactly_ten_keys(self) -> None:
        """Exactly 10 keys is valid."""
        extras = {f"key_{i}": "value" for i in range(10)}
        result = validate_extras(extras)
        assert len(result) == 10

    def test_validate_extras_too_large(self) -> None:
        """Serialized extras exceeding 4096 bytes should raise ValueError."""
        # Create a dict that serializes to more than 4096 bytes
        extras = {"large_value": "x" * 5000}
        with pytest.raises(ValueError, match="4096"):
            validate_extras(extras)

    def test_validate_extras_just_under_size_limit(self) -> None:
        """Extras just under the size limit should pass."""
        # JSON of {"v": "xxx..."} where total is under 4096
        extras = {"v": "x" * 4080}
        result = validate_extras(extras)
        assert result == extras
