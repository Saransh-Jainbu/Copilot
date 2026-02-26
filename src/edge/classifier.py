"""
Edge Layer: Failure Classifier
Classifies CI/CD failure logs into predefined categories.
Uses a rule-based approach with an optional transformer-based classifier.
"""

from dataclasses import dataclass
from typing import Optional

from src.edge.log_parser import LogParser, ParsedLog


@dataclass
class ClassificationResult:
    """Result of failure classification."""
    category: str
    confidence: float
    reasoning: str
    parsed_log: Optional[ParsedLog] = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "parsed_log": self.parsed_log.to_dict() if self.parsed_log else None,
        }


# Category keywords with weights for rule-based classification
CATEGORY_RULES = {
    "dependency_error": {
        "keywords": [
            "modulenotfounderror", "importerror", "no module named",
            "npm err", "could not resolve dependency", "peer dep",
            "pip install", "requirement", "package not found",
            "cannot find package", "missing dependency",
        ],
        "weight": 1.0,
    },
    "syntax_error": {
        "keywords": [
            "syntaxerror", "indentationerror", "taberror",
            "parse error", "unexpected token", "expected",
            "invalid syntax",
        ],
        "weight": 1.0,
    },
    "env_mismatch": {
        "keywords": [
            "version", "required", "unsupported", "incompatible",
            "mismatch", "not set", "missing", "undefined",
            "environment variable",
        ],
        "weight": 0.7,  # Lower weight — version/missing are ambiguous
    },
    "build_failure": {
        "keywords": [
            "build failed", "compilation error", "make error",
            "docker build", "dockerfile", "linker error",
            "cmake error", "failed to compile",
        ],
        "weight": 1.0,
    },
    "test_failure": {
        "keywords": [
            "test failed", "assertion", "assertionerror",
            "expect", "failed,", "passed", "pytest",
            "unittest", "test_", "spec failed",
        ],
        "weight": 0.9,
    },
    "timeout": {
        "keywords": [
            "timeout", "timed out", "exceeded", "deadline",
            "operation timed", "cancelled",
        ],
        "weight": 1.0,
    },
    "permission_error": {
        "keywords": [
            "permissionerror", "permission denied", "access denied",
            "eacces", "403", "unauthorized", "forbidden",
        ],
        "weight": 1.0,
    },
}


class FailureClassifier:
    """Classifies CI/CD failure logs using rule-based scoring.

    Optionally can be extended with a transformer-based classifier
    for higher accuracy.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.6,
        use_transformer: bool = False,
    ):
        self.confidence_threshold = confidence_threshold
        self.use_transformer = use_transformer
        self.parser = LogParser()

    def classify(self, raw_log: str) -> ClassificationResult:
        """Classify a raw CI/CD log into a failure category.

        Args:
            raw_log: The raw log text.

        Returns:
            ClassificationResult with category, confidence, and reasoning.
        """
        # Step 1: Parse the log
        parsed = self.parser.parse(raw_log)

        # Step 2: If parser already identified a type, use it as a strong signal
        parser_type = parsed.error_type

        # Step 3: Rule-based scoring
        scores = self._score_categories(raw_log)

        # Step 4: Boost the parser's classification
        if parser_type in scores:
            scores[parser_type] += 0.3

        # Step 5: Find the best category
        if scores:
            best_category = max(scores, key=scores.get)
            best_score = scores[best_category]

            # Normalize to 0-1 range using score-based sigmoid-like formula
            # This ensures even 1-2 keyword matches produce meaningful confidence
            confidence = min(best_score / (best_score + 1.0), 1.0)

            if confidence >= self.confidence_threshold:
                return ClassificationResult(
                    category=best_category,
                    confidence=round(confidence, 3),
                    reasoning=self._build_reasoning(best_category, scores),
                    parsed_log=parsed,
                )

        # Fallback to unknown
        return ClassificationResult(
            category="unknown",
            confidence=0.0,
            reasoning="No failure pattern matched with sufficient confidence.",
            parsed_log=parsed,
        )

    def _score_categories(self, log: str) -> dict[str, float]:
        """Score each category based on keyword matches."""
        log_lower = log.lower()
        scores: dict[str, float] = {}

        for category, rule in CATEGORY_RULES.items():
            score = 0.0
            for keyword in rule["keywords"]:
                if keyword in log_lower:
                    score += rule["weight"]
            if score > 0:
                scores[category] = score

        return scores

    def _build_reasoning(self, best_category: str, scores: dict[str, float]) -> str:
        """Build a human-readable reasoning string."""
        parts = [f"Best match: {best_category} (score: {scores[best_category]:.2f})"]
        other = {k: v for k, v in scores.items() if k != best_category and v > 0}
        if other:
            alt = ", ".join(f"{k}: {v:.2f}" for k, v in sorted(other.items(), key=lambda x: -x[1]))
            parts.append(f"Alternative matches: {alt}")
        return ". ".join(parts)

    def classify_batch(self, logs: list[str]) -> list[ClassificationResult]:
        """Classify multiple logs."""
        return [self.classify(log) for log in logs]
