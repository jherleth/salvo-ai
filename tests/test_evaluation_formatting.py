"""Tests for evaluation result formatting."""

from __future__ import annotations

import pytest

from salvo.evaluation.formatting import _describe_assertion, format_eval_results
from salvo.models.result import EvalResult


class TestDescribeAssertion:
    """Tests for _describe_assertion helper."""

    def test_jmespath_assertion(self):
        """JMESPath assertion shows path, operator, and expected value."""
        result = EvalResult(
            assertion_type="jmespath",
            score=1.0,
            passed=True,
            weight=1.0,
            required=False,
            details="path='response.content' operator=contains expected='hello' actual='hello world'",
        )
        desc = _describe_assertion(result)
        assert "response.content" in desc
        assert "contains" in desc
        assert "hello" in desc

    def test_tool_sequence_assertion(self):
        """Tool sequence assertion includes details."""
        result = EvalResult(
            assertion_type="tool_sequence",
            score=1.0,
            passed=True,
            weight=1.0,
            required=False,
            details="EXACT match: ['search', 'read']",
        )
        desc = _describe_assertion(result)
        assert "tool_sequence" in desc

    def test_cost_limit_assertion(self):
        """Cost limit assertion includes details."""
        result = EvalResult(
            assertion_type="cost_limit",
            score=1.0,
            passed=True,
            weight=1.0,
            required=False,
            details="Cost $0.0010 vs limit $0.0500",
        )
        desc = _describe_assertion(result)
        assert "cost_limit" in desc

    def test_latency_limit_assertion(self):
        """Latency limit assertion includes details."""
        result = EvalResult(
            assertion_type="latency_limit",
            score=1.0,
            passed=True,
            weight=1.0,
            required=False,
            details="Latency 2.500s vs limit 10.000s",
        )
        desc = _describe_assertion(result)
        assert "latency_limit" in desc


class TestFormatEvalResults:
    """Tests for format_eval_results."""

    def test_pass_not_verbose_shows_single_line(self):
        """On pass (not verbose), shows single score line."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=1.0,
                passed=True,
                weight=1.0,
                required=False,
                details="path='response.content' operator=contains expected='hello' actual='hello world'",
            ),
        ]
        output = format_eval_results(results, 1.0, 0.8, True, False, verbose=False)
        assert "PASS" in output
        assert "Score: 1.00 (>= 0.80)" in output
        # Should NOT have detailed breakdown
        assert "Score breakdown" not in output

    def test_pass_verbose_shows_all_assertions_and_breakdown(self):
        """On pass (verbose), shows all assertions and score breakdown."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=1.0,
                passed=True,
                weight=1.0,
                required=False,
                details="path='response.content' operator=contains expected='hello' actual='hello world'",
            ),
            EvalResult(
                assertion_type="cost_limit",
                score=1.0,
                passed=True,
                weight=0.5,
                required=False,
                details="Cost $0.0010 vs limit $0.0500",
            ),
        ]
        output = format_eval_results(results, 1.0, 0.8, True, False, verbose=True)
        assert "PASS" in output
        assert "Score breakdown" in output
        assert "PASS       " in output  # per-assertion pass lines
        assert "Total:" in output

    def test_fail_shows_severity_ordering(self):
        """On fail, hard failures shown first, then soft failures, then passes."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=1.0,
                passed=True,
                weight=1.0,
                required=False,
                details="path='x' operator=eq expected='y' actual='y'",
            ),
            EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=1.0,
                required=True,
                details="path='a' operator=eq expected='b' actual='c'",
            ),
            EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=1.0,
                required=False,
                details="path='d' operator=eq expected='e' actual='f'",
            ),
        ]
        output = format_eval_results(results, 0.33, 0.8, False, True)
        lines = output.split("\n")
        # Find the assertion lines
        assertion_lines = [l for l in lines if l.strip().startswith(("HARD FAIL", "FAILED", "PASS "))]
        assert len(assertion_lines) == 3
        assert assertion_lines[0].strip().startswith("HARD FAIL")
        assert assertion_lines[1].strip().startswith("FAILED")
        assert assertion_lines[2].strip().startswith("PASS")

    def test_hard_fail_shows_required_label(self):
        """Hard fail output shows 'HARD FAIL (required assertion failed)'."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=1.0,
                required=True,
                details="path='a' operator=eq expected='b' actual='c'",
            ),
        ]
        output = format_eval_results(results, 0.0, 0.8, False, True)
        assert "HARD FAIL (required assertion failed)" in output

    def test_score_breakdown_math_correct(self):
        """Score breakdown shows correct weighted calculation."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=1.0,
                passed=True,
                weight=2.0,
                required=False,
                details="path='a' operator=eq expected='b' actual='b'",
            ),
            EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=1.0,
                required=False,
                details="path='c' operator=eq expected='d' actual='e'",
            ),
        ]
        # score = (1.0*2.0 + 0.0*1.0) / (2.0 + 1.0) = 2.0/3.0 = 0.67
        score = 2.0 / 3.0
        output = format_eval_results(results, score, 0.8, False, False)
        assert "Total: 2.00 / 3.00 = 0.67" in output

    def test_soft_fail_shows_score_line(self):
        """Soft failure shows score below threshold."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=1.0,
                required=False,
                details="path='a' operator=eq expected='b' actual='c'",
            ),
        ]
        output = format_eval_results(results, 0.0, 0.8, False, False)
        assert "Score: 0.00 (< 0.80)  FAILED" in output

    def test_empty_results_pass(self):
        """Empty eval_results with pass shows minimal output."""
        output = format_eval_results([], 1.0, 0.8, True, False)
        assert "PASS" in output
        assert "Score breakdown" not in output

    def test_required_tag_in_breakdown(self):
        """Required assertions show [REQUIRED] tag in score breakdown."""
        results = [
            EvalResult(
                assertion_type="jmespath",
                score=0.0,
                passed=False,
                weight=1.0,
                required=True,
                details="path='a' operator=eq expected='b' actual='c'",
            ),
        ]
        output = format_eval_results(results, 0.0, 0.8, False, True)
        assert "[REQUIRED]" in output
