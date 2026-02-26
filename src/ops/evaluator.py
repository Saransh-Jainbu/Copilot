"""
Ops: Evaluator
Evaluates the quality of debugging responses.
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of evaluating a debugging response."""
    relevance: float       # 0-1: How relevant is the response to the error?
    completeness: float    # 0-1: Does it cover root cause + fix + prevention?
    actionability: float   # 0-1: Are suggestions specific and actionable?
    response_length: int   # Character count
    latency_ms: int        # End-to-end latency
    overall_score: float   # Weighted average

    def to_dict(self) -> dict:
        return {
            "relevance": self.relevance,
            "completeness": self.completeness,
            "actionability": self.actionability,
            "response_length": self.response_length,
            "latency_ms": self.latency_ms,
            "overall_score": self.overall_score,
        }


class Evaluator:
    """Evaluates debugging response quality using heuristic metrics.

    Can be extended with LLM-as-judge for more sophisticated evaluation.
    """

    def __init__(self):
        self.required_sections = [
            "root cause",
            "fix",
            "suggestion",
            "patch",
            "recommend",
        ]

    def evaluate(
        self,
        diagnosis: str,
        error_category: str,
        latency_ms: int,
    ) -> EvaluationResult:
        """Evaluate a debugging response.

        Args:
            diagnosis: The LLM-generated diagnosis text.
            error_category: The classified error category.
            latency_ms: End-to-end latency.

        Returns:
            EvaluationResult with scores.
        """
        relevance = self._score_relevance(diagnosis, error_category)
        completeness = self._score_completeness(diagnosis)
        actionability = self._score_actionability(diagnosis)

        overall = (
            relevance * 0.35 +
            completeness * 0.35 +
            actionability * 0.30
        )

        return EvaluationResult(
            relevance=round(relevance, 3),
            completeness=round(completeness, 3),
            actionability=round(actionability, 3),
            response_length=len(diagnosis),
            latency_ms=latency_ms,
            overall_score=round(overall, 3),
        )

    def _score_relevance(self, diagnosis: str, error_category: str) -> float:
        """Score how well the diagnosis relates to the error category."""
        lower = diagnosis.lower()
        category_keywords = {
            "dependency_error": ["dependency", "import", "module", "package", "install", "pip", "npm"],
            "syntax_error": ["syntax", "parse", "token", "indent", "unexpected"],
            "env_mismatch": ["version", "environment", "variable", "compatible", "mismatch"],
            "build_failure": ["build", "compile", "link", "cmake", "docker"],
            "test_failure": ["test", "assert", "expect", "fail", "pytest"],
            "timeout": ["timeout", "deadline", "slow", "performance"],
            "permission_error": ["permission", "access", "denied", "auth"],
        }

        keywords = category_keywords.get(error_category, [])
        if not keywords:
            return 0.5

        matches = sum(1 for kw in keywords if kw in lower)
        return min(matches / max(len(keywords) * 0.5, 1), 1.0)

    def _score_completeness(self, diagnosis: str) -> float:
        """Score whether the response covers all expected sections."""
        lower = diagnosis.lower()
        found = sum(1 for section in self.required_sections if section in lower)
        return found / len(self.required_sections)

    def _score_actionability(self, diagnosis: str) -> float:
        """Score how actionable the suggestions are."""
        score = 0.0
        lower = diagnosis.lower()

        # Check for numbered steps
        import re
        numbered = re.findall(r"^\s*\d+[\.\)]\s+", diagnosis, re.MULTILINE)
        if numbered:
            score += 0.3

        # Check for code blocks
        if "```" in diagnosis:
            score += 0.3

        # Check for specific commands
        command_keywords = ["run", "install", "add", "update", "change", "replace", "set", "remove"]
        cmd_matches = sum(1 for kw in command_keywords if kw in lower)
        score += min(cmd_matches / 4, 0.4)

        return min(score, 1.0)

    def evaluate_batch(
        self,
        results: list[dict],
    ) -> dict:
        """Evaluate a batch of results and return aggregate metrics.

        Args:
            results: List of dicts with keys: diagnosis, error_category, latency_ms.

        Returns:
            Aggregate metrics dict.
        """
        evaluations = [
            self.evaluate(
                r["diagnosis"],
                r["error_category"],
                r["latency_ms"],
            )
            for r in results
        ]

        if not evaluations:
            return {"count": 0}

        return {
            "count": len(evaluations),
            "avg_relevance": round(sum(e.relevance for e in evaluations) / len(evaluations), 3),
            "avg_completeness": round(sum(e.completeness for e in evaluations) / len(evaluations), 3),
            "avg_actionability": round(sum(e.actionability for e in evaluations) / len(evaluations), 3),
            "avg_overall": round(sum(e.overall_score for e in evaluations) / len(evaluations), 3),
            "avg_latency_ms": round(sum(e.latency_ms for e in evaluations) / len(evaluations)),
        }
