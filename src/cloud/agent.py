"""
Cloud Layer: Agent
LLM-powered debugging agent with tool-calling and self-critique capabilities.
Uses a multi-step reasoning workflow to analyze CI/CD failures.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.edge.classifier import FailureClassifier, ClassificationResult
from src.edge.preprocessor import LogPreprocessor
from src.edge.remediation_templates import get_remediation_template
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
            "step_number": self.step_number,
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
- **Subtype**: {error_subtype}
- **Error Lines**:
{error_lines}

## Extracted Evidence
{extracted_evidence}

## Diagnostic Guardrails
{diagnostic_guardrails}

## Stack Trace
{stack_trace}

## Relevant Documentation & Similar Past Errors
{retrieved_context}

## Raw Error Section
{error_section}

## Task
Analyze this CI/CD pipeline failure and provide:
1. **Root Cause Diagnosis**: What exactly went wrong and why.
2. **Fix Suggestions**: 3-5 actionable steps to fix this issue.
3. **Patch Recommendation**: If possible, suggest specific code or config changes.

Rules:
- Use the exact evidence from the log. Quote the most important failing line verbatim.
- Name the exact failing system or artifact when possible, such as image name, registry, package, hostname, file, secret, or workflow.
- Do not give generic advice like "check credentials" unless the log actually points to credentials.
- If the retrieved context is empty or says no relevant documentation was found, do not pretend documentation exists.
- Prefer the most specific root cause over broad categories.

Be specific, actionable, and reference the documentation when relevant.
Format your response with clear headers and bullet points.
"""

DOCKER_REGISTRY_AUTH_PROMPT = """You are DevOps Copilot, an expert in Docker and CI/CD registry failures.

## Error Classification
- **Type**: {error_type}
- **Subtype**: {error_subtype}
- **Confidence**: {confidence}

## Exact Failing Evidence
- **Primary Error**: {error_message}
- **Error Lines**:
{error_lines}
- **Extracted Evidence**:
{extracted_evidence}

## Relevant Documentation & Similar Past Errors
{retrieved_context}

## Raw Error Section
{error_section}

## Task
Produce a diagnosis specifically for a Docker registry authentication failure.

Required reasoning constraints:
- State clearly that the failure happens while resolving or pulling the base image, before normal Dockerfile build steps execute.
- Name the exact image and registry when present.
- Prioritize only these likely causes unless the log contradicts them:
    1. stale or invalid Docker Hub credentials or token
    2. CI secret misconfiguration or missing docker login step
    3. broken credential helper, remote builder auth config, or registry mirror/proxy issue
- Mention that even public images can fail this way if the builder is sending broken auth.

Do not suggest these unless the log explicitly supports them:
- wrong image tag or deleted image
- Dockerfile syntax issues
- missing files in build context
- generic firewall/network advice

Provide:
1. **Root Cause Diagnosis**
2. **Fix Suggestions**: 3-5 highly specific steps
3. **Patch Recommendation**: only CI or auth-related changes if applicable

Format with clear headers and bullet points.
"""

DOCKER_IMAGE_NOT_FOUND_PROMPT = """You are DevOps Copilot, an expert in Docker image resolution failures.

## Error Classification
- **Type**: {error_type}
- **Subtype**: {error_subtype}
- **Confidence**: {confidence}

## Exact Failing Evidence
- **Primary Error**: {error_message}
- **Error Lines**:
{error_lines}
- **Extracted Evidence**:
{extracted_evidence}

## Relevant Documentation & Similar Past Errors
{retrieved_context}

## Raw Error Section
{error_section}

## Task
Produce a diagnosis specifically for a Docker image-not-found failure.

Required reasoning constraints:
- Focus on wrong tag, wrong repository name, deleted image, or wrong registry path.
- Do not focus on credentials unless the log explicitly shows auth failure.
- Mention the exact image reference from the log.

Provide:
1. **Root Cause Diagnosis**
2. **Fix Suggestions**
3. **Patch Recommendation**

Format with clear headers and bullet points.
"""

K8S_INGRESS_ADMISSION_CERT_PROMPT = """You are DevOps Copilot, an expert in Kubernetes admission webhook TLS failures.

## Error Classification
- **Type**: {error_type}
- **Subtype**: {error_subtype}
- **Confidence**: {confidence}

## Exact Failing Evidence
- **Primary Error**: {error_message}
- **Error Lines**:
{error_lines}
- **Extracted Evidence**:
{extracted_evidence}

## Relevant Documentation & Similar Past Errors
{retrieved_context}

## Raw Error Section
{error_section}

## Task
Produce a diagnosis specifically for ingress-nginx admission webhook certificate trust failures.

Required reasoning constraints:
- Explain this is a Kubernetes API server -> admission webhook TLS trust problem, not an app container/client cert problem.
- Mention that `x509: certificate signed by unknown authority` usually means webhook certificate/caBundle drift or stale admission secret.
- Mention the failing webhook/service name when present.
- Prioritize fixes around ingress-nginx admission cert regeneration and ValidatingWebhookConfiguration caBundle patch.

Do not suggest generic client certificate replacement unless log evidence explicitly indicates client-auth TLS.

Provide:
1. **Root Cause Diagnosis**
2. **Fix Suggestions**: 3-5 highly specific kubectl/helm-oriented steps
3. **Patch Recommendation**: concrete commands or manifest fields (caBundle, webhook config, ingress-nginx admission secret)

Format with clear headers and bullet points.
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

LOW_CONFIDENCE_ABSTAIN_PROMPT = """You are DevOps Copilot, an expert CI/CD debugging assistant.

The error classifier could not identify this failure with high confidence.

## Error Classification Attempt
- **Best-guess Category**: {error_type}
- **Classifier Confidence**: {confidence} (below threshold — partial diagnosis)

## Available Evidence
- **Error Message**: {error_message}
- **Error Lines**:
{error_lines}
- **Extracted Evidence**:
{extracted_evidence}

## Relevant Documentation
{retrieved_context}

## Raw Error Section
{error_section}

## Task
Provide a **partial diagnosis with explicit uncertainty**.

Your response MUST include:
1. **Most Likely Cause** — your best guess even under uncertainty; clearly label it as "probable" or "possible".
2. **Supporting Evidence** — which lines or signals in the log support this hypothesis.
3. **Missing Evidence** — what additional information (env vars, full trace, tool version, config snippet) would confirm or refute the diagnosis.
4. **Next Debugging Steps** — concrete steps the user can take to gather the missing evidence.

Do NOT produce a confident diagnosis when you lack evidence. Prefer honest uncertainty over false precision.
Format with clear headers and bullet points.
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
        enable_self_critique: bool = False,
        low_confidence_threshold: float = 0.45,
    ):
        self.llm = llm_client or LLMClient()
        self.classifier = classifier or FailureClassifier()
        self.retriever = retriever or Retriever()
        self.preprocessor = preprocessor or LogPreprocessor()
        self.max_reasoning_steps = max_reasoning_steps
        self.enable_self_critique = enable_self_critique
        self.low_confidence_threshold = low_confidence_threshold
        self.max_context_results = max(int(os.getenv("AGENT_MAX_CONTEXT_RESULTS", "3")), 1)
        self.max_context_chars = max(int(os.getenv("AGENT_MAX_CONTEXT_CHARS", "2000")), 500)
        self.max_error_section_chars = max(int(os.getenv("AGENT_MAX_ERROR_SECTION_CHARS", "2000")), 500)
        self.max_diagnosis_tokens = max(int(os.getenv("AGENT_MAX_DIAGNOSIS_TOKENS", "320")), 64)
        self.max_critique_tokens = max(int(os.getenv("AGENT_MAX_CRITIQUE_TOKENS", "96")), 32)

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
        if classification.parsed_log and isinstance(classification.parsed_log.metadata, dict):
            # Persist category so suggestion templates can be applied consistently.
            classification.parsed_log.metadata["category"] = classification.category
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
        query = self._build_retrieval_query(classification, cleaned_log)
        rerank_terms = self._build_rerank_terms(classification)
        retrieval = self.retriever.retrieve(query, rerank_terms=rerank_terms)
        context_str = retrieval.to_context_string(max_results=self.max_context_results)
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
        prompt = self._build_diagnosis_prompt(
            classification=classification,
            parsed=parsed,
            retrieved_context=context_str,
            error_section=error_section,
        )

        llm_response = self.llm.generate(prompt, max_tokens=self.max_diagnosis_tokens)
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
            critique_response = self.llm.generate(
                critique_prompt,
                max_tokens=self.max_critique_tokens,
            )
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
        fix_suggestions = self._filter_suggestions(fix_suggestions, parsed)
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

    def _build_retrieval_query(
        self,
        classification: ClassificationResult,
        cleaned_log: str,
    ) -> str:
        """Build a retrieval query from the most concrete failure evidence."""
        parsed = classification.parsed_log
        query_parts = [classification.category]

        if parsed and parsed.error_message:
            query_parts.append(parsed.error_message)

        if parsed and parsed.error_lines:
            query_parts.extend(parsed.error_lines[:3])

        if parsed and parsed.metadata.get("ecosystems"):
            query_parts.extend(parsed.metadata["ecosystems"])

        subtype = self._extract_error_subtype(parsed)
        if subtype != "N/A":
            query_parts.append(subtype)

        if parsed and parsed.metadata.get("docker_images"):
            query_parts.extend(parsed.metadata["docker_images"][:3])

        if parsed and parsed.metadata.get("docker_registries"):
            query_parts.extend(parsed.metadata["docker_registries"][:3])

        if parsed and parsed.metadata.get("http_statuses"):
            query_parts.extend(parsed.metadata["http_statuses"][:3])

        failing_instruction = parsed.metadata.get("failing_instruction") if parsed else None
        if failing_instruction:
            query_parts.append(failing_instruction)

        if parsed and parsed.file_path:
            query_parts.append(parsed.file_path)

        if len(query_parts) == 1:
            query_parts.append(cleaned_log[:500])

        return " | ".join(part.strip() for part in query_parts if part and part.strip())

    def _build_rerank_terms(self, classification: ClassificationResult) -> list[str]:
        """Build a list of high-signal exact-match terms for retrieval reranking.

        These terms (image names, HTTP codes, registries, subtype labels) are
        used to boost documents whose content mentions the exact failing artifact.
        """
        parsed = classification.parsed_log
        terms: list[str] = [classification.category]

        subtype = self._extract_error_subtype(parsed)
        if subtype != "N/A":
            terms.append(subtype)

        if parsed:
            if parsed.error_message:
                # Add individual high-signal tokens from the error message.
                for word in parsed.error_message.split():
                    if len(word) > 5 and word not in terms:
                        terms.append(word)

            if parsed.metadata.get("docker_images"):
                terms.extend(parsed.metadata["docker_images"][:3])

            if parsed.metadata.get("docker_registries"):
                terms.extend(parsed.metadata["docker_registries"][:3])

            if parsed.metadata.get("http_statuses"):
                terms.extend(parsed.metadata["http_statuses"][:3])

            if parsed.metadata.get("failing_instruction"):
                terms.append(parsed.metadata["failing_instruction"])

        return [t for t in terms if t and len(t) > 2]

    def _extract_error_subtype(self, parsed: Optional[Any]) -> str:
        """Extract a normalized subtype string from parsed metadata."""
        if not parsed:
            return "N/A"
        metadata = parsed.metadata if hasattr(parsed, "metadata") and isinstance(parsed.metadata, dict) else {}
        return metadata.get("docker_subtype") or metadata.get("network_ssl_subtype") or "N/A"

    def _build_diagnosis_prompt(
        self,
        classification: ClassificationResult,
        parsed: Optional[Any],
        retrieved_context: str,
        error_section: str,
    ) -> str:
        """Build the most appropriate diagnosis prompt for the current failure."""
        prompt_template = self._select_diagnosis_prompt(classification.category, parsed, classification.confidence)
        params = dict(
            error_type=classification.category,
            confidence=classification.confidence,
            error_message=parsed.error_message if parsed else "N/A",
            error_lines="\n".join(parsed.error_lines[:6]) if parsed else "N/A",
            extracted_evidence=self._format_extracted_evidence(parsed),
            retrieved_context=self._truncate_text(retrieved_context, self.max_context_chars),
            error_section=error_section[: self.max_error_section_chars] if error_section else "N/A",
        )
        # Full diagnosis prompts need extra params; only add them when template uses them.
        if prompt_template not in (LOW_CONFIDENCE_ABSTAIN_PROMPT,):
            params.update(
                exit_code=parsed.exit_code if parsed else "N/A",
                file_path=parsed.file_path if parsed else "N/A",
                line_number=parsed.line_number if parsed else "N/A",
                error_subtype=self._extract_error_subtype(parsed),
                diagnostic_guardrails=self._build_diagnostic_guardrails(parsed),
                stack_trace="\n".join(parsed.stack_trace[:8]) if parsed else "N/A",
            )
        return prompt_template.format(**params)

    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate large prompt sections to keep LLM requests responsive."""
        if not text or len(text) <= max_chars:
            return text
        return text[: max_chars - 15].rstrip() + "\n...[truncated]"

    def _select_diagnosis_prompt(
        self,
        category: str,
        parsed: Optional[Any],
        confidence: float = 1.0,
    ) -> str:
        """Choose a category-specific prompt when a specialized one exists."""
        if confidence < self.low_confidence_threshold:
            return LOW_CONFIDENCE_ABSTAIN_PROMPT
        subtype = self._extract_error_subtype(parsed)
        if category == "docker_container" and subtype == "registry_auth":
            return DOCKER_REGISTRY_AUTH_PROMPT
        if category == "docker_container" and subtype == "image_not_found":
            return DOCKER_IMAGE_NOT_FOUND_PROMPT
        if category == "network_ssl" and subtype == "k8s_ingress_admission_cert":
            return K8S_INGRESS_ADMISSION_CERT_PROMPT
        return DIAGNOSIS_PROMPT

    def _format_extracted_evidence(self, parsed: Optional[Any]) -> str:
        """Format extracted structured evidence for the prompt."""
        if not parsed:
            return "N/A"

        lines = []
        subtype = parsed.metadata.get("docker_subtype")
        if subtype:
            lines.append(f"- Docker subtype: {subtype}")

        images = parsed.metadata.get("docker_images", [])
        if images:
            lines.append(f"- Docker images: {', '.join(images[:5])}")

        registries = parsed.metadata.get("docker_registries", [])
        if registries:
            lines.append(f"- Docker registries: {', '.join(registries[:5])}")

        http_statuses = parsed.metadata.get("http_statuses", [])
        if http_statuses:
            lines.append(f"- HTTP statuses: {', '.join(http_statuses[:5])}")

        dockerfile_line = parsed.metadata.get("dockerfile_line")
        if dockerfile_line:
            lines.append(f"- Dockerfile line: {dockerfile_line}")

        failing_instruction = parsed.metadata.get("failing_instruction")
        if failing_instruction:
            lines.append(f"- Failing instruction: {failing_instruction}")

        stages = parsed.metadata.get("docker_build_stages", [])
        if stages:
            stage_summary = ", ".join(
                f"#{stage['step']} [{stage['name']}]" for stage in stages[:5]
            )
            lines.append(f"- Build stages: {stage_summary}")

        ecosystems = parsed.metadata.get("ecosystems", [])
        if ecosystems:
            lines.append(f"- Ecosystems: {', '.join(ecosystems)}")

        return "\n".join(lines) if lines else "N/A"

    def _build_diagnostic_guardrails(self, parsed: Optional[Any]) -> str:
        """Build evidence-aware guardrails to keep the diagnosis specific."""
        if not parsed:
            return "- Stay grounded in the log evidence."

        subtype = parsed.metadata.get("docker_subtype")
        guardrails = ["- Base the diagnosis on the exact failing line and extracted evidence."]

        if subtype == "registry_auth":
            guardrails.extend([
                "- Prioritize Docker registry authentication, stale credentials, token flow, or registry mirror/proxy issues.",
                "- Do not suggest image tag problems unless the log shows manifest not found or image not found.",
                "- Do not suggest build context or Dockerfile syntax issues unless the log mentions COPY, ADD, or parse errors.",
            ])
        elif subtype == "image_not_found":
            guardrails.extend([
                "- Prioritize missing image tag, wrong repository name, or deleted image.",
                "- Do not suggest credential rotation unless the log shows authorization failure.",
            ])
        elif subtype == "build_context_missing":
            guardrails.extend([
                "- Focus on missing files in build context, .dockerignore exclusions, or wrong COPY paths.",
                "- Do not suggest registry auth unless the log shows pull or authorize failures.",
            ])
        elif subtype == "k8s_ingress_admission_cert":
            guardrails.extend([
                "- Focus on ingress admission webhook CA trust mismatch (caBundle vs served cert) and stale admission cert secrets.",
                "- Do not frame this as application TLS client-certificate failure unless explicit client-auth evidence exists.",
                "- Prioritize webhook configuration and ingress-nginx admission certificate rotation/remediation.",
            ])

        return "\n".join(guardrails)

    def _extract_suggestions(self, text: str) -> list[str]:
        """Extract numbered suggestions from LLM output."""
        lines = text.split("\n")
        suggestions: list[str] = []

        # Prefer extracting from the explicit "Fix Suggestions" section.
        start_idx = None
        for i, line in enumerate(lines):
            if "fix suggestions" in line.lower():
                start_idx = i + 1
                break

        candidate_lines: list[str]
        if start_idx is not None:
            scoped: list[str] = []
            for line in lines[start_idx:]:
                stripped = line.strip()
                if stripped.startswith("## ") and scoped:
                    break
                scoped.append(line)
            candidate_lines = scoped
        else:
            candidate_lines = lines

        for line in candidate_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if (
                (stripped[0].isdigit() and len(stripped) > 2 and stripped[1] in ".)") or
                stripped.startswith("- ") or
                stripped.startswith("* ")
            ):
                cleaned = stripped.lstrip("0123456789.)- *").strip()
                cleaned = cleaned.replace("**", "").strip()
                if cleaned:
                    suggestions.append(cleaned)

        return suggestions[:10]

    def _extract_patch(self, text: str) -> str:
        """Extract code patch content from LLM output."""
        # Look for code blocks
        import re
        code_blocks = re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)
        if code_blocks:
            return "\n\n".join(code_blocks)
        return "No specific patch generated. See fix suggestions above."

    def _filter_suggestions(self, suggestions: list[str], parsed: Optional[Any]) -> list[str]:
        """Filter low-relevance LLM suggestions using subtype-aware heuristics.

        Always prepends deterministic template suggestions as a quality floor,
        then appends non-overlapping filtered LLM suggestions up to 10 total.
        """
        category = getattr(getattr(parsed, "metadata", {}), "get", lambda k, d=None: d)("category", "")
        if parsed and hasattr(parsed, "metadata"):
            category = parsed.metadata.get("category", "")
        subtype = self._extract_error_subtype(parsed)
        subtype_for_template = subtype if subtype != "N/A" else None

        # Deterministic quality floor from remediation templates.
        template_items = get_remediation_template(category, subtype_for_template)

        if not suggestions:
            return template_items or self._default_suggestions_for_subtype(parsed)

        if subtype != "registry_auth":
            # Merge: template first, then non-duplicate LLM items.
            return self._merge_suggestions(template_items, suggestions, max_total=10)

        evidence_blob = " ".join(
            [
                parsed.error_message if parsed else "",
                " ".join(parsed.error_lines) if parsed else "",
                " ".join(parsed.context_lines) if parsed else "",
                " ".join(parsed.metadata.get("http_statuses", [])) if parsed else "",
            ]
        ).lower()

        allow_network = any(
            marker in evidence_blob
            for marker in [
                "econn", "timeout", "timed out", "dns", "enotfound",
                "connection refused", "ssl", "tls",
            ]
        )

        filtered: list[str] = []
        for suggestion in suggestions:
            s = suggestion.lower()

            # Suppress common off-target advice for registry auth failures.
            if any(term in s for term in ["dockerfile syntax", "syntax issue", "parse error"]):
                continue
            if any(term in s for term in ["build context", "copy path", ".dockerignore"]):
                continue
            if any(term in s for term in ["image tag", "deleted image", "manifest not found"]):
                continue
            if ("firewall" in s or "network" in s) and not allow_network:
                continue

            filtered.append(suggestion)

        base = template_items or self._default_suggestions_for_subtype(parsed)
        return self._merge_suggestions(base, filtered, max_total=10)

    def _merge_suggestions(
        self,
        base: list[str],
        extras: list[str],
        max_total: int = 10,
    ) -> list[str]:
        """Merge two suggestion lists, deduplicating extras against base."""
        seen = {item.strip().lower() for item in base}
        result = list(base)
        for item in extras:
            key = item.strip().lower()
            if key and key not in seen and len(result) < max_total:
                result.append(item)
                seen.add(key)
        return result

    def _default_suggestions_for_subtype(self, parsed: Optional[Any]) -> list[str]:
        """Provide deterministic fallback suggestions for known subtypes."""
        subtype = self._extract_error_subtype(parsed)
        if subtype == "registry_auth":
            return [
                "Validate Docker Hub credentials/token in CI and rotate token if expired.",
                "Add an explicit docker login step before docker build using CI secrets.",
                "Clear stale Docker auth state on the runner or remote builder and retry.",
                "If using a registry mirror/proxy, bypass it temporarily to isolate auth flow issues.",
            ]
        return []
