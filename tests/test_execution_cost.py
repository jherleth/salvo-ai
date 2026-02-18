"""Tests for cost estimation from token usage."""

from __future__ import annotations

import pytest

from salvo.execution.cost import estimate_cost


class TestEstimateCostGPT4o:
    """Test cost estimation for gpt-4o model."""

    def test_estimate_cost_gpt4o(self) -> None:
        """gpt-4o: (1000/1M * 2.50) + (500/1M * 10.00) = 0.0075"""
        result = estimate_cost("gpt-4o", 1000, 500)
        assert result is not None
        assert result == pytest.approx(0.0075)

    def test_estimate_cost_gpt4o_large_usage(self) -> None:
        """gpt-4o with larger token counts."""
        result = estimate_cost("gpt-4o", 10000, 5000)
        assert result is not None
        assert result == pytest.approx(0.075)


class TestEstimateCostGPT4oMini:
    """Test cost estimation for gpt-4o-mini model."""

    def test_estimate_cost_gpt4o_mini(self) -> None:
        """gpt-4o-mini: (1000/1M * 0.15) + (500/1M * 0.60) = 0.00045"""
        result = estimate_cost("gpt-4o-mini", 1000, 500)
        assert result is not None
        assert result == pytest.approx(0.00045)


class TestEstimateCostClaude:
    """Test cost estimation for Claude models."""

    def test_estimate_cost_claude_sonnet(self) -> None:
        """claude-sonnet-4-5: (1000/1M * 3.00) + (500/1M * 15.00) = 0.0105"""
        result = estimate_cost("claude-sonnet-4-5", 1000, 500)
        assert result is not None
        assert result == pytest.approx(0.0105)

    def test_estimate_cost_claude_haiku(self) -> None:
        """claude-haiku-4-5: (1000/1M * 1.00) + (500/1M * 5.00) = 0.0035"""
        result = estimate_cost("claude-haiku-4-5", 1000, 500)
        assert result is not None
        assert result == pytest.approx(0.0035)


class TestEstimateCostEdgeCases:
    """Test edge cases for cost estimation."""

    def test_estimate_cost_unknown_model_returns_none(self) -> None:
        """Unknown models return None instead of raising."""
        result = estimate_cost("unknown-model", 1000, 500)
        assert result is None

    def test_estimate_cost_zero_tokens(self) -> None:
        """Zero tokens should return 0.0 for known models."""
        result = estimate_cost("gpt-4o", 0, 0)
        assert result is not None
        assert result == 0.0


class TestEstimateCostModelAliases:
    """Test that dated model aliases resolve correctly."""

    def test_claude_sonnet_dated_alias(self) -> None:
        """claude-sonnet-4-5-20250929 should resolve to same pricing as claude-sonnet-4-5."""
        result = estimate_cost("claude-sonnet-4-5-20250929", 1000, 500)
        assert result is not None
        assert result == pytest.approx(0.0105)

    def test_claude_haiku_dated_alias(self) -> None:
        """claude-haiku-4-5-20241022 should resolve to same pricing as claude-haiku-4-5."""
        result = estimate_cost("claude-haiku-4-5-20241022", 1000, 500)
        assert result is not None
        assert result == pytest.approx(0.0035)
