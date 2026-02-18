"""Tests for assertion normalizer."""

from __future__ import annotations

import pytest

from salvo.evaluation.normalizer import normalize_assertion, normalize_assertions


class TestNormalizeAssertion:
    """Test normalize_assertion converts shorthand to canonical form."""

    @pytest.mark.parametrize("op", ["eq", "ne", "gt", "gte", "lt", "lte", "contains", "regex"])
    def test_operator_key_shorthand_expands_to_canonical(self, op: str) -> None:
        raw = {"path": "response.content", op: "expected_value"}
        result = normalize_assertion(raw)
        assert result["type"] == "jmespath"
        assert result["expression"] == "response.content"
        assert result["operator"] == op
        assert result["value"] == "expected_value"
        assert result["weight"] == 1.0
        assert result["required"] is False

    def test_explicit_type_key_passes_through(self) -> None:
        raw = {
            "type": "tool_sequence",
            "mode": "exact",
            "sequence": ["search", "answer"],
            "weight": 2.0,
            "required": True,
        }
        result = normalize_assertion(raw)
        assert result == raw

    def test_default_path_is_response_content(self) -> None:
        raw = {"contains": "hello"}
        result = normalize_assertion(raw)
        assert result["expression"] == "response.content"

    def test_weight_carries_over(self) -> None:
        raw = {"path": "metadata.model", "eq": "gpt-4", "weight": 3.0}
        result = normalize_assertion(raw)
        assert result["weight"] == 3.0

    def test_required_carries_over(self) -> None:
        raw = {"path": "metadata.model", "eq": "gpt-4", "required": True}
        result = normalize_assertion(raw)
        assert result["required"] is True

    def test_error_on_multiple_operator_keys(self) -> None:
        raw = {"path": "response.content", "eq": "a", "contains": "b"}
        with pytest.raises(ValueError, match="multiple operator"):
            normalize_assertion(raw)

    def test_error_on_no_type_and_no_operator(self) -> None:
        raw = {"path": "response.content", "weight": 1.0}
        with pytest.raises(ValueError, match="no .* operator"):
            normalize_assertion(raw)


class TestNormalizeAssertions:
    """Test normalize_assertions maps over a list."""

    def test_maps_over_list(self) -> None:
        raw_list = [
            {"eq": "hello"},
            {"type": "cost_limit", "max_usd": 0.10},
        ]
        results = normalize_assertions(raw_list)
        assert len(results) == 2
        assert results[0]["type"] == "jmespath"
        assert results[0]["operator"] == "eq"
        assert results[1]["type"] == "cost_limit"

    def test_empty_list(self) -> None:
        assert normalize_assertions([]) == []
