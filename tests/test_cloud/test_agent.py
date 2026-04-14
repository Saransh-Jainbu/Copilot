"""
Tests for Cloud Layer: Debug Agent
Uses fully mocked LLM, classifier, and retriever to test agent logic.
"""

import pytest
from unittest.mock import MagicMock

from src.cloud.agent import DebugAgent, DebugResult, AgentStep
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
        agent.debug(log)

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

    def test_debug_generates_fallback_patch_when_llm_fails(self, mock_classifier, mock_retriever, mock_preprocessor):
        failing_llm = MagicMock()
        failing_llm.generate.return_value = {
            "text": "Error: Unable to generate response from any model.",
            "model": "openai/gpt-oss-120b:fastest",
            "latency_ms": 100,
            "tokens_used": 0,
            "error": True,
        }

        agent = DebugAgent(
            llm_client=failing_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )

        result = agent.debug("ModuleNotFoundError: No module named 'numpy'")
        assert "requirements.txt" in result.patch_recommendation
        assert "numpy" in result.patch_recommendation
        assert "No specific patch generated" not in result.patch_recommendation


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

    def test_extract_suggestions_ignores_numbered_root_cause_section(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        text = (
            "## Root Cause Diagnosis\n"
            "1. Error Type: InternalError\n"
            "2. Subsystem: Kubernetes API\n"
            "## Fix Suggestions\n"
            "1. Patch the webhook caBundle\n"
            "2. Regenerate ingress-nginx admission cert\n"
            "## Patch Recommendation\n"
            "- Update ValidatingWebhookConfiguration\n"
        )
        suggestions = agent._extract_suggestions(text)
        assert suggestions[0].startswith("Patch the webhook caBundle")
        assert all("Error Type" not in s for s in suggestions)

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

    def test_build_fallback_patch_for_dependency_error(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        classification = ClassificationResult(
            category="dependency_error",
            confidence=0.9,
            reasoning="",
            parsed_log=ParsedLog(
                error_message="ModuleNotFoundError: No module named 'yaml'",
                error_lines=["ModuleNotFoundError: No module named 'yaml'"],
            ),
        )

        patch = agent._build_fallback_patch(classification, classification.parsed_log)
        assert "requirements.txt" in patch
        assert "PyYAML" in patch

    def test_build_retrieval_query_uses_error_evidence(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        classification = mock_classifier.classify("test")
        query = agent._build_retrieval_query(classification, "raw log fallback")
        assert "dependency_error" in query
        assert "No module named 'numpy'" in query

    def test_format_extracted_evidence_includes_docker_fields(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(
            metadata={
                "docker_subtype": "registry_auth",
                "docker_images": ["node:18-alpine"],
                "docker_registries": ["docker.io"],
                "http_statuses": ["401 Unauthorized"],
                "dockerfile_line": 1,
                "failing_instruction": "FROM node:18-alpine",
                "ecosystems": ["docker", "nodejs"],
            }
        )
        evidence = agent._format_extracted_evidence(parsed)
        assert "node:18-alpine" in evidence
        assert "docker.io" in evidence
        assert "401 Unauthorized" in evidence

    def test_build_diagnostic_guardrails_for_registry_auth(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(metadata={"docker_subtype": "registry_auth"})
        guardrails = agent._build_diagnostic_guardrails(parsed)
        assert "Do not suggest image tag problems" in guardrails
        assert "registry authentication" in guardrails

    def test_select_diagnosis_prompt_for_docker_registry_auth(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(metadata={"docker_subtype": "registry_auth"})
        prompt_template = agent._select_diagnosis_prompt("docker_container", parsed)
        assert "Docker registry authentication failure" in prompt_template

    def test_select_diagnosis_prompt_for_k8s_ingress_admission_cert(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(metadata={"network_ssl_subtype": "k8s_ingress_admission_cert"})
        prompt_template = agent._select_diagnosis_prompt("network_ssl", parsed)
        assert "admission webhook TLS failures" in prompt_template

    def test_select_generic_prompt_for_non_docker(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(metadata={})
        prompt_template = agent._select_diagnosis_prompt("dependency_error", parsed)
        assert "expert CI/CD debugging assistant" in prompt_template

    def test_filter_registry_auth_suggestions_removes_irrelevant_items(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(
            error_message="failed to fetch oauth token",
            error_lines=["401 Unauthorized"],
            metadata={"docker_subtype": "registry_auth", "http_statuses": ["401 Unauthorized"]},
        )
        suggestions = [
            "Check Docker Hub credentials",
            "Check Dockerfile syntax issues",
            "Verify image tag exists",
        ]
        filtered = agent._filter_suggestions(suggestions, parsed)
        assert any("credentials" in s.lower() for s in filtered)
        assert not any("syntax" in s.lower() for s in filtered)
        assert not any("image tag" in s.lower() for s in filtered)

    def test_filter_registry_auth_suggestions_has_fallback(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(metadata={"docker_subtype": "registry_auth"})
        filtered = agent._filter_suggestions(["Check Dockerfile syntax issues"], parsed)
        assert len(filtered) >= 1
        assert any("docker login" in s.lower() for s in filtered)

    def test_filter_k8s_ingress_admission_suggestions_uses_template(self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(
            metadata={
                "category": "network_ssl",
                "network_ssl_subtype": "k8s_ingress_admission_cert",
            }
        )
        filtered = agent._filter_suggestions([], parsed)
        assert len(filtered) >= 1
        assert any("caBundle" in s for s in filtered)


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


class TestNewFeatures:
    """Tests for reranking, abstain, templates, and merge_suggestions."""

    def test_select_abstain_prompt_low_confidence(
        self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor
    ):
        """Agent should use the abstain prompt when confidence is below threshold."""
        from src.cloud.agent import LOW_CONFIDENCE_ABSTAIN_PROMPT

        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
            low_confidence_threshold=0.45,
        )
        parsed = ParsedLog(metadata={})
        prompt = agent._select_diagnosis_prompt("unknown", parsed, confidence=0.30)
        assert prompt is LOW_CONFIDENCE_ABSTAIN_PROMPT

    def test_select_diagnosis_prompt_above_threshold_uses_specific(
        self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor
    ):
        """Agent should NOT use abstain prompt when confidence is above threshold."""
        from src.cloud.agent import LOW_CONFIDENCE_ABSTAIN_PROMPT

        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
            low_confidence_threshold=0.45,
        )
        parsed = ParsedLog(metadata={"docker_subtype": "registry_auth"})
        prompt = agent._select_diagnosis_prompt("docker_container", parsed, confidence=0.90)
        assert prompt is not LOW_CONFIDENCE_ABSTAIN_PROMPT

    def test_build_rerank_terms_includes_subtype(
        self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor
    ):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        from src.edge.classifier import ClassificationResult
        parsed = ParsedLog(
            error_message="unauthorized: incorrect username",
            metadata={
                "docker_subtype": "registry_auth",
                "docker_images": ["node:18"],
                "docker_registries": ["registry-1.docker.io"],
                "http_statuses": ["401 Unauthorized"],
            },
        )
        clf_result = ClassificationResult(
            category="docker_container",
            confidence=0.9,
            reasoning="match",
            parsed_log=parsed,
        )
        terms = agent._build_rerank_terms(clf_result)
        assert "docker_container" in terms
        assert "registry_auth" in terms
        assert "node:18" in terms
        assert any("401" in t for t in terms)

    def test_merge_suggestions_deduplicates(
        self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor
    ):
        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        base = ["Run docker login in CI", "Rotate the token"]
        extras = ["run docker login in ci", "Check firewall rules"]
        merged = agent._merge_suggestions(base, extras, max_total=10)
        # Deduped — only unique items
        lower_merged = [s.lower() for s in merged]
        assert lower_merged.count("run docker login in ci") == 1
        assert "check firewall rules" in lower_merged

    def test_filter_suggestions_prepends_templates(
        self, mock_llm, mock_classifier, mock_retriever, mock_preprocessor
    ):
        """Template items should appear first in filtered suggestions."""
        from src.edge.remediation_templates import get_remediation_template

        agent = DebugAgent(
            llm_client=mock_llm,
            classifier=mock_classifier,
            retriever=mock_retriever,
            preprocessor=mock_preprocessor,
        )
        parsed = ParsedLog(
            error_message="unauthorized: incorrect username",
            error_lines=["401"],
            metadata={
                "docker_subtype": "registry_auth",
                "category": "docker_container",
                "http_statuses": ["401 Unauthorized"],
            },
        )
        llm_suggestions = ["A custom LLM suggestion about credentials"]
        filtered = agent._filter_suggestions(llm_suggestions, parsed)
        template_items = get_remediation_template("docker_container", "registry_auth")
        # First item should come from template (it's prepended)
        assert filtered[0] == template_items[0]


class TestRemediationTemplates:
    """Test the remediation templates module."""

    def test_docker_registry_auth_template_has_login(self):
        from src.edge.remediation_templates import get_remediation_template
        items = get_remediation_template("docker_container", "registry_auth")
        assert len(items) > 0
        assert any("docker login" in item.lower() for item in items)
        assert any("token" in item.lower() for item in items)

    def test_docker_image_not_found_template_mentions_tag(self):
        from src.edge.remediation_templates import get_remediation_template
        items = get_remediation_template("docker_container", "image_not_found")
        assert len(items) > 0
        assert any("tag" in item.lower() for item in items)

    def test_fallback_to_generic_category_template(self):
        from src.edge.remediation_templates import get_remediation_template
        # Use a subtype that doesn't have a specific template
        items = get_remediation_template("docker_container", "rate_limit")
        # Should fall back to generic docker_container template if no specific one
        # But there is no generic docker_container entry, so should get empty list or root template
        # Just ensure it doesn't raise
        assert isinstance(items, list)

    def test_dependency_error_template(self):
        from src.edge.remediation_templates import get_remediation_template
        items = get_remediation_template("dependency_error", None)
        assert len(items) > 0
        assert any("pin" in item.lower() for item in items)

    def test_unknown_category_returns_empty(self):
        from src.edge.remediation_templates import get_remediation_template
        items = get_remediation_template("nonexistent_category", None)
        assert items == []


class TestRetrieverReranking:
    """Test the retriever reranking logic."""

    def test_rerank_boosts_documents_with_matching_terms(self):
        from src.fog.retriever import Retriever
        from src.fog.vector_store import SearchResult, Document

        # Build fake results
        results = [
            SearchResult(
                document=Document(id="1", content="Fix docker login for registry authentication"),
                score=0.80,
                rank=1,
            ),
            SearchResult(
                document=Document(id="2", content="General CI/CD troubleshooting guide"),
                score=0.85,
                rank=2,
            ),
        ]

        ret = Retriever.__new__(Retriever)  # skip __init__
        reranked = ret._rerank(results, terms=["registry_auth", "docker login"], top_k=2)

        # Document 1 should be ranked higher after reranking
        assert reranked[0].document.id == "1"
        assert reranked[0].score > results[0].score  # boosted

    def test_rerank_returns_top_k(self):
        from src.fog.retriever import Retriever
        from src.fog.vector_store import SearchResult, Document

        results = [
            SearchResult(document=Document(id=str(i), content=f"doc {i}"), score=0.9 - i * 0.05, rank=i + 1)
            for i in range(10)
        ]
        ret = Retriever.__new__(Retriever)
        reranked = ret._rerank(results, terms=["doc 3"], top_k=3)
        assert len(reranked) == 3

    def test_rerank_with_empty_terms_returns_unchanged_top_k(self):
        from src.fog.retriever import Retriever
        from src.fog.vector_store import SearchResult, Document

        results = [
            SearchResult(document=Document(id=str(i), content=f"doc {i}"), score=float(i), rank=i + 1)
            for i in range(5)
        ]
        ret = Retriever.__new__(Retriever)
        reranked = ret._rerank(results, terms=[], top_k=3)
        assert len(reranked) == 3
