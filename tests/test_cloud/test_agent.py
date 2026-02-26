"""
Tests for Cloud Layer: Debug Agent
Uses fully mocked LLM, classifier, and retriever to test agent logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from src.cloud.agent import DebugAgent, DebugResult, AgentStep, AgentAction
from src.edge.classifier import ClassificationResult
from src.edge.log_parser import ParsedLog
from src.fog.retriever import RetrievalResult
from src.fog.vector_store import SearchResult, Document


# ---- Fixtures ----

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate.return_value = {
        "text": (
            "### Root Cause Diagnosis\n"
            "The error is caused by a missing numpy package.\n\n"
            "### Fix Suggestions\n"
            "1. Run pip install numpy to install the missing package\n"
            "2. Add numpy to requirements.txt\n"
            "3. Pin the version: numpy>=1.24.0\n\n"
            "### Patch Recommendation\n"
            "```\nnumpy>=1.24.0\n```\n\n"
            "APPROVED confidence: 0.85"
        ),
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "latency_ms": 1500,
        "tokens_used": 200,
        "error": False,
    }
    return llm


@pytest.fixture
def mock_classifier():
    clf = MagicMock()
    clf.classify.return_value = ClassificationResult(
        category="dependency_error",
        confidence=0.95,
        reasoning="Best match: dependency_error (score: 2.0)",
        parsed_log=ParsedLog(
            error_type="dependency_error",
            error_message="No module named 'numpy'",
            error_lines=["ModuleNotFoundError: No module named 'numpy'"],
            exit_code=1,
        ),
    )
    return clf


@pytest.fixture
def mock_retriever():
    ret = MagicMock()
    ret.retrieve.return_value = RetrievalResult(
        query="dependency_error numpy",
        results=[
            SearchResult(
                document=Document(
                    id="d1",
                    content="Fix ModuleNotFoundError by running pip install <module>",
                    source="docs/python.md",
                ),
                score=0.88,
                rank=1,
            )
        ],
        total_candidates=50,
    )
    return ret


@pytest.fixture
def mock_preprocessor():
    pp = MagicMock()
    pp.preprocess.side_effect = lambda x, **kw: x  # pass-through
    pp.extract_error_section.side_effect = lambda x, **kw: x
    return pp


# ---- Agent Tests ----

class TestDebugAgent:
    """Test the debugging agent logic."""

    def test_debug_returns_result(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
            max_reasoning_steps=5,
            enable_self_critique=True,
        )

        log = "ModuleNotFoundError: No module named 'numpy'\n##[error]Process completed with exit code 1."
        result = agent.debug(log)

        assert isinstance(result, DebugResult)
        assert result.classification.category == "dependency_error"
        assert result.confidence > 0
        assert len(result.reasoning_trace) > 0
        assert result.total_latency_ms >= 0

    def test_debug_calls_all_stages(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )

        log = "SyntaxError: invalid syntax"
        result = agent.debug(log)

        # Should have called classifier and retriever
        mock_classifier.classify.assert_called_once()
        mock_retriever.retrieve.assert_called_once()
        # Should have called LLM at least once (diagnosis)
        assert mock_llm.generate.call_count >= 1

    def test_debug_without_self_critique(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
            enable_self_critique=False,
        )

        log = "npm ERR! ERESOLVE unable to resolve dependency tree"
        result = agent.debug(log)

        assert isinstance(result, DebugResult)
        # Without self-critique, fewer LLM calls expected
        assert result.total_latency_ms >= 0


# ---- Helper Method Tests ----

class TestAgentHelpers:
    """Test agent helper methods."""

    def test_extract_suggestions(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        text = "1. Install numpy\n2. Update requirements.txt\n3. Pin versions"
        suggestions = agent._extract_suggestions(text)
        assert len(suggestions) >= 3
        assert "Install numpy" in suggestions[0]

    def test_extract_patch(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        text = "Some explanation\n```\nnumpy>=1.24.0\nflask>=2.0\n```\nMore text."
        patch = agent._extract_patch(text)
        assert "numpy" in patch


# ---- Data Class Tests ----

class TestAgentDataClasses:
    """Test serialization of agent data classes."""

    def test_agent_step_to_dict(self):
        step = AgentStep(
            step_number=1,
            action="classify",
            input_summary="raw log text",
            output_summary="dependency_error",
            latency_ms=50,
        )
        d = step.to_dict()
        assert d["step_number"] == 1
        assert d["action"] == "classify"
        assert "latency_ms" in d

    def test_debug_result_to_dict(self, mock_classifier):
        result = DebugResult(
            classification=mock_classifier.classify("test"),
            retrieved_context=RetrievalResult(query="q", results=[], total_candidates=0),
            diagnosis="Test diagnosis",
            fix_suggestions=["Fix 1", "Fix 2"],
            patch_recommendation="patch code",
            confidence=0.85,
            reasoning_trace=[],
            total_latency_ms=2000,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "classification" in d
        assert "diagnosis" in d
        assert "fix_suggestions" in d
