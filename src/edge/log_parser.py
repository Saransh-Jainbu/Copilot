"""
Edge Layer: Log Parser
Parses raw CI/CD failure logs and extracts structured error information.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedLog:
    """Structured representation of a parsed CI/CD failure log."""
    error_type: str = "unknown"
    error_message: str = ""
    error_lines: list[str] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)
    exit_code: Optional[int] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    stack_trace: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_lines": self.error_lines,
            "context_lines": self.context_lines,
            "exit_code": self.exit_code,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata,
        }


# --- Regex Patterns for Common CI/CD Errors ---

PATTERNS = {
    "dependency_error": [
        re.compile(r"(?i)(ModuleNotFoundError|ImportError|No module named)\s*[:\-]?\s*(.+)"),
        re.compile(r"(?i)(npm ERR!|Could not resolve dependency|peer dep missing)\s*(.*)"),
        re.compile(r"(?i)(pip install.*failed|requirement.*not satisfied)\s*(.*)"),
        re.compile(r"(?i)(Package .+ not found|cannot find package)\s*(.*)"),
    ],
    "syntax_error": [
        re.compile(r"(?i)(SyntaxError|IndentationError|TabError)\s*[:\-]?\s*(.+)"),
        re.compile(r"(?i)(Parse error|Unexpected token)\s*[:\-]?\s*(.+)"),
        re.compile(r"(?i)(error: expected .+ but found)\s*(.+)"),
    ],
    "env_mismatch": [
        re.compile(r"(?i)(python|node|java|go) version .+ (required|expected|needed)"),
        re.compile(r"(?i)(unsupported .+ version|version mismatch|incompatible version)\s*(.*)"),
        re.compile(r"(?i)(env|environment) variable .+ (not set|missing|undefined)"),
    ],
    "build_failure": [
        re.compile(r"(?i)(build failed|compilation error|make.*error)\s*(.*)"),
        re.compile(r"(?i)(error\[E\d+\]|FAILED:.*)\s*(.*)"),
        re.compile(r"(?i)(docker build.*failed|Dockerfile.*error)\s*(.*)"),
    ],
    "test_failure": [
        re.compile(r"(?i)(FAILED|FAIL)\s+(test[_\w]*|[\w/]+test[\w]*)\s*(.*)"),
        re.compile(r"(?i)(AssertionError|assertion failed|expect.*to)\s*(.*)"),
        re.compile(r"(?i)(\d+ failed,?\s*\d+ passed)\s*(.*)"),
    ],
    "timeout": [
        re.compile(r"(?i)(timeout|timed out|exceeded .+ seconds)\s*(.*)"),
        re.compile(r"(?i)(deadline exceeded|operation.*timed out)\s*(.*)"),
    ],
    "permission_error": [
        re.compile(r"(?i)(PermissionError|permission denied|access denied)\s*(.*)"),
        re.compile(r"(?i)(EACCES|403 Forbidden|unauthorized)\s*(.*)"),
    ],
}

EXIT_CODE_PATTERN = re.compile(r"(?:exit code|exited with|return code)[:\s]+(\d+)", re.IGNORECASE)
FILE_LINE_PATTERN = re.compile(r"(?:File|at)\s+[\"']?([^\s\"':]+)[\"']?\s*(?:,\s*line\s+(\d+))?")
STACK_TRACE_PATTERN = re.compile(r"^\s+(at\s+|File\s+|Traceback|\.{3})", re.MULTILINE)
ERROR_LINE_PATTERN = re.compile(r"(?i)^.*(?:error|fail|fatal|exception|critical).*$", re.MULTILINE)


class LogParser:
    """Parses raw CI/CD logs into structured error reports."""

    def __init__(self, max_context_lines: int = 50):
        self.max_context_lines = max_context_lines

    def parse(self, raw_log: str) -> ParsedLog:
        """Parse a raw CI/CD log string into a structured ParsedLog."""
        result = ParsedLog()

        # Extract error lines
        result.error_lines = self._extract_error_lines(raw_log)

        # Extract exit code
        result.exit_code = self._extract_exit_code(raw_log)

        # Extract file path and line number
        file_info = self._extract_file_info(raw_log)
        if file_info:
            result.file_path, result.line_number = file_info

        # Extract stack trace
        result.stack_trace = self._extract_stack_trace(raw_log)

        # Classify error type and extract message
        result.error_type, result.error_message = self._classify_and_extract(raw_log)

        # Extract context lines around errors
        result.context_lines = self._extract_context(raw_log)

        # Extract metadata
        result.metadata = self._extract_metadata(raw_log)

        return result

    def _extract_error_lines(self, log: str) -> list[str]:
        """Extract lines containing error keywords."""
        matches = ERROR_LINE_PATTERN.findall(log)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for line in matches:
            stripped = line.strip()
            if stripped not in seen and len(stripped) > 5:
                seen.add(stripped)
                unique.append(stripped)
        return unique[:20]  # Cap at 20 error lines

    def _extract_exit_code(self, log: str) -> Optional[int]:
        """Extract process exit code from log."""
        match = EXIT_CODE_PATTERN.search(log)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _extract_file_info(self, log: str) -> Optional[tuple[str, Optional[int]]]:
        """Extract file path and line number from error location."""
        match = FILE_LINE_PATTERN.search(log)
        if match:
            file_path = match.group(1)
            line_num = int(match.group(2)) if match.group(2) else None
            return file_path, line_num
        return None

    def _extract_stack_trace(self, log: str) -> list[str]:
        """Extract stack trace frames from log."""
        lines = log.split("\n")
        trace_lines = []
        in_trace = False

        for line in lines:
            if "Traceback" in line or "stack trace" in line.lower():
                in_trace = True
                trace_lines.append(line.strip())
            elif in_trace:
                if line.strip() and (line.startswith("  ") or line.startswith("\t") or
                                     STACK_TRACE_PATTERN.match(line)):
                    trace_lines.append(line.strip())
                elif line.strip() and not line.startswith(" "):
                    # End of indented trace block — include the final error line
                    trace_lines.append(line.strip())
                    in_trace = False
                else:
                    in_trace = False

        return trace_lines[:30]  # Cap at 30 lines

    def _classify_and_extract(self, log: str) -> tuple[str, str]:
        """Classify the error type and extract the primary error message."""
        for error_type, patterns in PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(log)
                if match:
                    message = match.group(0).strip()
                    return error_type, message

        # Fallback: look for generic error lines
        error_lines = ERROR_LINE_PATTERN.findall(log)
        if error_lines:
            return "unknown", error_lines[0].strip()

        return "unknown", "No specific error pattern matched"

    def _extract_context(self, log: str) -> list[str]:
        """Extract context lines surrounding error occurrences."""
        lines = log.split("\n")
        context = []
        error_indices = []

        for i, line in enumerate(lines):
            if ERROR_LINE_PATTERN.match(line):
                error_indices.append(i)

        # Gather context around each error
        context_radius = min(5, self.max_context_lines // max(len(error_indices), 1))
        for idx in error_indices[:5]:  # Max 5 error locations
            start = max(0, idx - context_radius)
            end = min(len(lines), idx + context_radius + 1)
            for line in lines[start:end]:
                stripped = line.strip()
                if stripped and stripped not in context:
                    context.append(stripped)

        return context[:self.max_context_lines]

    def _extract_metadata(self, log: str) -> dict:
        """Extract CI/CD platform metadata from log."""
        metadata = {}

        # Detect platform
        if "##[group]" in log or "::error::" in log:
            metadata["platform"] = "github_actions"
        elif "gitlab-runner" in log.lower():
            metadata["platform"] = "gitlab_ci"
        elif "jenkins" in log.lower():
            metadata["platform"] = "jenkins"
        else:
            metadata["platform"] = "unknown"

        # Count total lines
        metadata["total_lines"] = len(log.split("\n"))

        # Detect language/ecosystem hints
        ecosystems = []
        if any(kw in log.lower() for kw in ["pip", "python", ".py", "pytest"]):
            ecosystems.append("python")
        if any(kw in log.lower() for kw in ["npm", "node", "yarn", ".js", ".ts"]):
            ecosystems.append("nodejs")
        if any(kw in log.lower() for kw in ["docker", "dockerfile", "container"]):
            ecosystems.append("docker")
        if any(kw in log.lower() for kw in ["go build", "go test", ".go"]):
            ecosystems.append("go")
        if any(kw in log.lower() for kw in ["mvn", "gradle", ".java", "pom.xml"]):
            ecosystems.append("java")
        metadata["ecosystems"] = ecosystems

        return metadata
