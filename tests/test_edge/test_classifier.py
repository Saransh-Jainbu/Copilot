"""
Tests for Edge Layer: Failure Classifier
"""

import pytest
from src.edge.classifier import FailureClassifier


@pytest.fixture
def classifier():
    return FailureClassifier(confidence_threshold=0.3)


class TestFailureClassifier:
    """Test suite for the failure classifier."""

    def test_classify_dependency_error(self, classifier):
        log = "ModuleNotFoundError: No module named 'requests'"
        result = classifier.classify(log)
        assert result.category == "dependency_error"
        assert result.confidence > 0

    def test_classify_syntax_error(self, classifier):
        log = "SyntaxError: invalid syntax at line 42"
        result = classifier.classify(log)
        assert result.category == "syntax_error"

    def test_classify_build_failure(self, classifier):
        log = "build failed: compilation error in main.cpp"
        result = classifier.classify(log)
        assert result.category == "build_failure"

    def test_classify_test_failure(self, classifier):
        log = "FAILED tests/test_auth.py - AssertionError: assert 200 == 401\n2 failed, 3 passed"
        result = classifier.classify(log)
        assert result.category == "test_failure"

    def test_classify_timeout(self, classifier):
        log = "Error: operation timed out after 300 seconds"
        result = classifier.classify(log)
        assert result.category == "timeout"

    def test_classify_permission_error(self, classifier):
        log = "PermissionError: permission denied: /usr/local/bin"
        result = classifier.classify(log)
        assert result.category == "permission_error"

    def test_classify_unknown(self, classifier):
        log = "Everything is fine, no errors here."
        result = classifier.classify(log)
        assert result.category == "unknown"

    def test_classification_has_reasoning(self, classifier):
        log = "npm ERR! Could not resolve dependency tree"
        result = classifier.classify(log)
        assert result.reasoning
        assert len(result.reasoning) > 0

    def test_classify_batch(self, classifier):
        logs = [
            "ModuleNotFoundError: No module named 'flask'",
            "SyntaxError: unexpected token",
            "build failed with errors",
        ]
        results = classifier.classify_batch(logs)
        assert len(results) == 3
        assert results[0].category == "dependency_error"
        assert results[1].category == "syntax_error"

    def test_to_dict(self, classifier):
        log = "npm ERR! package not found"
        result = classifier.classify(log)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "category" in d
        assert "confidence" in d
        assert "reasoning" in d
