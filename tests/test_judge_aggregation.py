"""Tests for judge k-vote aggregation."""

from __future__ import annotations

from salvo.evaluation.judge.aggregation import aggregate_k_votes


CRITERIA_TWO = [
    {"name": "accuracy", "description": "Factually correct", "weight": 1.0},
    {"name": "clarity", "description": "Easy to understand", "weight": 0.5},
]


def _make_vote(scores: dict[str, float]) -> dict:
    """Create a single k-vote result dict."""
    return {
        name: {"score": score, "reasoning": "test"}
        for name, score in scores.items()
    }


class TestAggregateKVotes:
    def test_aggregate_single_vote_pass(self):
        votes = [_make_vote({"accuracy": 0.9, "clarity": 0.8})]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.8)
        assert passed is True
        assert score > 0.0

    def test_aggregate_single_vote_fail(self):
        votes = [_make_vote({"accuracy": 0.3, "clarity": 0.2})]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.8)
        assert passed is False
        assert score < 0.8

    def test_aggregate_three_votes_majority_pass(self):
        votes = [
            _make_vote({"accuracy": 0.9, "clarity": 0.9}),  # pass
            _make_vote({"accuracy": 0.9, "clarity": 0.8}),  # pass
            _make_vote({"accuracy": 0.3, "clarity": 0.2}),  # fail
        ]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.8)
        assert passed is True  # 2/3 majority

    def test_aggregate_three_votes_majority_fail(self):
        votes = [
            _make_vote({"accuracy": 0.9, "clarity": 0.9}),  # pass
            _make_vote({"accuracy": 0.3, "clarity": 0.2}),  # fail
            _make_vote({"accuracy": 0.4, "clarity": 0.3}),  # fail
        ]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.8)
        assert passed is False  # 1/3 majority

    def test_aggregate_median_robust_to_outlier(self):
        votes = [
            _make_vote({"accuracy": 0.8, "clarity": 0.7}),
            _make_vote({"accuracy": 0.8, "clarity": 0.7}),
            _make_vote({"accuracy": 0.1, "clarity": 0.1}),  # outlier
        ]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.7)
        # Median of [0.8, 0.8, 0.1] = 0.8 for accuracy
        accuracy_detail = next(d for d in details if d["name"] == "accuracy")
        assert accuracy_detail["median_score"] == 0.8

    def test_aggregate_weighted_criteria(self):
        votes = [
            _make_vote({"accuracy": 1.0, "clarity": 0.0}),
        ]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.5)
        # Weighted: (1.0 * 1.0 + 0.0 * 0.5) / (1.0 + 0.5) = 1.0/1.5 ~= 0.667
        assert abs(score - (1.0 / 1.5)) < 0.01

    def test_aggregate_empty_results(self):
        score, passed, details = aggregate_k_votes([], CRITERIA_TWO, threshold=0.8)
        assert score == 0.0
        assert passed is False
        assert details == []

    def test_aggregate_missing_criterion_scores(self):
        # One vote has accuracy but not clarity
        votes = [
            _make_vote({"accuracy": 0.9}),
            _make_vote({"accuracy": 0.8, "clarity": 0.7}),
        ]
        score, passed, details = aggregate_k_votes(votes, CRITERIA_TWO, threshold=0.5)
        # Clarity: from vote 2 only -- median([0.7]) = 0.7 (missing vote has no score)
        clarity_detail = next(d for d in details if d["name"] == "clarity")
        assert len(clarity_detail["all_scores"]) == 1  # only one vote had clarity

    def test_aggregate_zero_weight_guard(self):
        zero_weight_criteria = [
            {"name": "a", "description": "test", "weight": 0.0},
            {"name": "b", "description": "test", "weight": 0.0},
        ]
        votes = [_make_vote({"a": 0.5, "b": 0.5})]
        score, passed, details = aggregate_k_votes(
            votes, zero_weight_criteria, threshold=0.5
        )
        assert score == 0.0
        assert passed is False
