"""
Tests for Ops Layer: Evaluator
"""

import pytest
from src.ops.evaluator import Evaluator, EvaluationResult


@pytest.fixture
def evaluator():
    return Evaluator()


class TestEvaluator:
    """Test evaluation scoring functions."""

    def test_evaluate_good_response(self, evaluator):
        diagnosis = (
            "### Root Cause\n"
            "The dependency error is caused by a missing numpy package.\n\n"
            "### Fix Suggestions\n"
            "1. Run `pip install numpy` to install the package\n"
            "2. Add numpy to your requirements.txt\n"
            "3. Update your Dockerfile to install dependencies\n\n"
            "### Patch Recommendation\n"
            "```\nnumpy>=1.24.0\n```\n"
        )
        result = evaluator.evaluate(diagnosis, "dependency_error", latency_ms=1500)

        assert isinstance(result, EvaluationResult)
        assert result.relevance > 0.5  # Should detect dependency keywords
        assert result.completeness > 0.0  # Has some required sections
        assert result.actionability > 0.0  # Has numbered steps and code blocks
        assert result.overall_score > 0.0

    def test_evaluate_empty_response(self, evaluator):
        result = evaluator.evaluate("", "unknown", latency_ms=100)
        assert result.relevance <= 0.5
        assert result.completeness == 0.0
        assert result.actionability == 0.0

    def test_evaluate_latency_tracked(self, evaluator):
        result = evaluator.evaluate("test fix suggestions", "build_failure", latency_ms=3000)
        assert result.latency_ms == 3000
        assert result.response_length == len("test fix suggestions")

    def test_relevance_scoring(self, evaluator):
        dep_diag = "The dependency import module package install pip npm failed."
        result = evaluator.evaluate(dep_diag, "dependency_error", latency_ms=100)
        assert result.relevance > 0.5

    def test_unknown_category_gives_default_relevance(self, evaluator):
        result = evaluator.evaluate("Some text", "nonexistent_category", latency_ms=100)
        assert result.relevance == 0.5  # Default for unknown categories

    def test_to_dict(self, evaluator):
        result = evaluator.evaluate("fix suggestion patch recommendation", "build_failure", latency_ms=500)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "relevance" in d
        assert "completeness" in d
        assert "actionability" in d
        assert "overall_score" in d

    def test_evaluate_batch(self, evaluator):
        results = [
            {"diagnosis": "Run pip install numpy to fix the dependency error", "error_category": "dependency_error", "latency_ms": 1000},
            {"diagnosis": "Fix the syntax by adding a semicolon", "error_category": "syntax_error", "latency_ms": 800},
        ]
        summary = evaluator.evaluate_batch(results)
        assert summary["count"] == 2
        assert "avg_relevance" in summary
        assert "avg_overall" in summary

    def test_evaluate_batch_empty(self, evaluator):
        summary = evaluator.evaluate_batch([])
        assert summary["count"] == 0
