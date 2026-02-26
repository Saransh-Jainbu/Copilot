"""
Cloud Layer: Agent
LLM-powered debugging agent with tool-calling and self-critique capabilities.
Uses a multi-step reasoning workflow to analyze CI/CD failures.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.edge.classifier import FailureClassifier, ClassificationResult
from src.edge.preprocessor import LogPreprocessor
from src.fog.retriever import Retriever, RetrievalResult
from src.cloud.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AgentAction(Enum):
    """Actions the agent can take."""
    CLASSIFY = "classify"
    RETRIEVE = "retrieve"
    REASON = "reason"
    SELF_CRITIQUE = "self_critique"
    FINALIZE = "finalize"


@dataclass
class AgentStep:
    """A single step in the agent's reasoning chain."""
    step_number: int
    action: str
    input_summary: str
    output_summary: str
    latency_ms: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step": self.step_number,
            "action": self.action,
            "input": self.input_summary,
            "output": self.output_summary,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


@dataclass
class DebugResult:
    """Final output from the debugging agent."""
    classification: ClassificationResult
    retrieved_context: RetrievalResult
    diagnosis: str
    fix_suggestions: list[str]
    patch_recommendation: str
    confidence: float
    reasoning_trace: list[AgentStep]
    total_latency_ms: int

    def to_dict(self) -> dict:
        return {
            "classification": self.classification.to_dict(),
            "diagnosis": self.diagnosis,
            "fix_suggestions": self.fix_suggestions,
            "patch_recommendation": self.patch_recommendation,
            "confidence": self.confidence,
            "reasoning_trace": [s.to_dict() for s in self.reasoning_trace],
            "total_latency_ms": self.total_latency_ms,
        }


# --- Prompt Templates ---

DIAGNOSIS_PROMPT = """You are DevOps Copilot, an expert CI/CD debugging assistant.

## Error Classification
- **Type**: {error_type}
- **Confidence**: {confidence}
- **Error Message**: {error_message}

## Parsed Error Details
- **Exit Code**: {exit_code}
- **File**: {file_path}
- **Line**: {line_number}
- **Error Lines**:
{error_lines}

## Stack Trace
{stack_trace}

## Relevant Documentation & Similar Past Errors
{retrieved_context}

## Task
Analyze this CI/CD pipeline failure and provide:
1. **Root Cause Diagnosis**: What exactly went wrong and why.
2. **Fix Suggestions**: 3-5 actionable steps to fix this issue.
3. **Patch Recommendation**: If possible, suggest specific code or config changes.

Be specific, actionable, and reference the documentation when relevant.
Format your response with clear headers and bullet points.
"""

SELF_CRITIQUE_PROMPT = """You are reviewing a debugging analysis for accuracy and completeness.

## Original Error
{error_summary}

## Proposed Diagnosis
{diagnosis}

## Review Checklist
1. Is the root cause correctly identified?
2. Are the fix suggestions actionable and complete?
3. Is the patch recommendation correct?
4. Are there any edge cases or alternative causes missed?

Provide a brief critique and an improved version if needed.
If the analysis is correct, respond with "APPROVED" followed by a confidence score (0-1).
"""


class DebugAgent:
    """Autonomous debugging agent using multi-step reasoning.

    Workflow:
    1. Preprocess the raw log
    2. Classify the failure type (Edge)
    3. Retrieve relevant documentation (Fog)
    4. Generate diagnosis and fix suggestions (Cloud/LLM)
    5. Self-critique and refine (optional)
    6. Return structured result
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        classifier: FailureClassifier | None = None,
        retriever: Retriever | None = None,
        preprocessor: LogPreprocessor | None = None,
        max_reasoning_steps: int = 5,
        enable_self_critique: bool = True,
    ):
        self.llm = llm_client or LLMClient()
        self.classifier = classifier or FailureClassifier()
        self.retriever = retriever or Retriever()
        self.preprocessor = preprocessor or LogPreprocessor()
        self.max_reasoning_steps = max_reasoning_steps
        self.enable_self_critique = enable_self_critique

    def debug(self, raw_log: str) -> DebugResult:
        """Run the full debugging pipeline on a raw CI/CD log.

        Args:
            raw_log: The raw CI/CD failure log text.

        Returns:
            DebugResult with diagnosis, suggestions, and reasoning trace.
        """
        total_start = time.time()
        trace: list[AgentStep] = []
        step_num = 0

        # --- Step 1: Preprocess ---
        step_num += 1
        step_start = time.time()
        cleaned_log = self.preprocessor.preprocess(raw_log, max_lines=200)
        error_section = self.preprocessor.extract_error_section(cleaned_log)
        trace.append(AgentStep(
            step_number=step_num,
            action=AgentAction.CLASSIFY.value,
            input_summary=f"Raw log ({len(raw_log)} chars)",
            output_summary=f"Cleaned to {len(cleaned_log)} chars, error section: {len(error_section)} chars",
            latency_ms=int((time.time() - step_start) * 1000),
        ))

        # --- Step 2: Classify ---
        step_num += 1
        step_start = time.time()
        classification = self.classifier.classify(cleaned_log)
        trace.append(AgentStep(
            step_number=step_num,
            action=AgentAction.CLASSIFY.value,
            input_summary=f"Cleaned log ({len(cleaned_log)} chars)",
            output_summary=f"Category: {classification.category} (conf: {classification.confidence})",
            latency_ms=int((time.time() - step_start) * 1000),
            metadata={"category": classification.category, "confidence": classification.confidence},
        ))

        # --- Step 3: Retrieve ---
        step_num += 1
        step_start = time.time()
        query = f"{classification.category}: {classification.reasoning}"
        retrieval = self.retriever.retrieve(query)
        context_str = retrieval.to_context_string()
        trace.append(AgentStep(
            step_number=step_num,
            action=AgentAction.RETRIEVE.value,
            input_summary=f"Query: '{query[:80]}...'",
            output_summary=f"Retrieved {len(retrieval.results)} docs from {retrieval.total_candidates} candidates",
            latency_ms=int((time.time() - step_start) * 1000),
            metadata={"num_results": len(retrieval.results)},
        ))

        # --- Step 4: LLM Reasoning ---
        step_num += 1
        step_start = time.time()
        parsed = classification.parsed_log
        prompt = DIAGNOSIS_PROMPT.format(
            error_type=classification.category,
            confidence=classification.confidence,
            error_message=parsed.error_message if parsed else "N/A",
            exit_code=parsed.exit_code if parsed else "N/A",
            file_path=parsed.file_path if parsed else "N/A",
            line_number=parsed.line_number if parsed else "N/A",
            error_lines="\n".join(parsed.error_lines[:10]) if parsed else "N/A",
            stack_trace="\n".join(parsed.stack_trace[:15]) if parsed else "N/A",
            retrieved_context=context_str,
        )

        llm_response = self.llm.generate(prompt)
        diagnosis_text = llm_response["text"]
        trace.append(AgentStep(
            step_number=step_num,
            action=AgentAction.REASON.value,
            input_summary=f"Prompt ({len(prompt)} chars)",
            output_summary=f"Generated {len(diagnosis_text)} chars ({llm_response['latency_ms']}ms)",
            latency_ms=llm_response["latency_ms"],
            metadata={"model": llm_response["model"], "tokens": llm_response["tokens_used"]},
        ))

        # --- Step 5: Self-Critique (optional) ---
        confidence = classification.confidence
        if self.enable_self_critique and step_num < self.max_reasoning_steps:
            step_num += 1
            step_start = time.time()
            critique_prompt = SELF_CRITIQUE_PROMPT.format(
                error_summary=f"{classification.category}: {parsed.error_message if parsed else 'N/A'}",
                diagnosis=diagnosis_text[:1500],
            )
            critique_response = self.llm.generate(critique_prompt)
            critique_text = critique_response["text"]

            if "APPROVED" in critique_text.upper():
                # Extract confidence if present
                try:
                    conf_str = critique_text.upper().split("APPROVED")[1].strip()
                    confidence = float(conf_str.split()[0].strip("().,"))
                except (ValueError, IndexError):
                    confidence = min(classification.confidence + 0.1, 1.0)
            else:
                # Use critique as improved diagnosis
                diagnosis_text = critique_text

            trace.append(AgentStep(
                step_number=step_num,
                action=AgentAction.SELF_CRITIQUE.value,
                input_summary=f"Diagnosis review ({len(diagnosis_text)} chars)",
                output_summary=f"Critique: {'APPROVED' if 'APPROVED' in critique_text.upper() else 'REVISED'}",
                latency_ms=int((time.time() - step_start) * 1000),
            ))

        # --- Parse results ---
        fix_suggestions = self._extract_suggestions(diagnosis_text)
        patch = self._extract_patch(diagnosis_text)

        total_ms = int((time.time() - total_start) * 1000)

        return DebugResult(
            classification=classification,
            retrieved_context=retrieval,
            diagnosis=diagnosis_text,
            fix_suggestions=fix_suggestions,
            patch_recommendation=patch,
            confidence=confidence,
            reasoning_trace=trace,
            total_latency_ms=total_ms,
        )

    def _extract_suggestions(self, text: str) -> list[str]:
        """Extract numbered suggestions from LLM output."""
        suggestions = []
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            # Match numbered items like "1.", "2)", "- "
            if stripped and (
                (stripped[0].isdigit() and len(stripped) > 2 and stripped[1] in ".)") or
                stripped.startswith("- ") or
                stripped.startswith("* ")
            ):
                suggestions.append(stripped.lstrip("0123456789.)- *").strip())
        return suggestions[:10]

    def _extract_patch(self, text: str) -> str:
        """Extract code patch content from LLM output."""
        # Look for code blocks
        import re
        code_blocks = re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)
        if code_blocks:
            return "\n\n".join(code_blocks)
        return "No specific patch generated. See fix suggestions above."
