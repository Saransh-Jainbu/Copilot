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
    "docker_container": [
        re.compile(r"(?i)(failed to fetch oauth token|failed to authorize|failed to resolve source metadata)\s*(.*)"),
        re.compile(r"(?i)(docker\.io|pull access denied|unauthorized: authentication required)\s*(.*)"),
        re.compile(r"(?i)(manifest for .+ not found|imagepullbackoff|errimagepull)\s*(.*)"),
    ],
    "kubernetes": [
        re.compile(r"(?i)(CrashLoopBackOff|ImagePullBackOff|ErrImagePull|OOMKilled)\s*(.*)"),
        re.compile(r"(?i)(liveness probe failed|readiness probe failed|pod stuck in pending)\s*(.*)"),
    ],
    "test_failure": [
        re.compile(r"(?i)(FAILED|FAIL)\s+(test[_\w]*|[\w/]+test[\w]*)\s*(.*)"),
        re.compile(r"(?i)(AssertionError|assertion failed|expect.*to)\s*(.*)"),
        re.compile(r"(?i)(\d+ failed,?\s*\d+ passed)\s*(.*)"),
    ],
    "timeout": [
        re.compile(r"(?i)(timed out|timeout after|timeout exceeded|exceeded .+ seconds)\s*(.*)"),
        re.compile(r"(?i)(deadline exceeded|operation.*timed out)\s*(.*)"),
    ],
    "permission_error": [
        re.compile(r"(?i)(PermissionError|permission denied|access denied)\s*(.*)"),
        re.compile(r"(?i)(EACCES|403 Forbidden|unauthorized)\s*(.*)"),
    ],
    "git_vcs": [
        re.compile(r"(?i)(fatal: could not read Username|failed to push some refs|revision .+ not found)\s*(.*)"),
        re.compile(r"(?i)(detached HEAD|submodule|git lfs)\s*(.*)"),
    ],
    "network_ssl": [
        re.compile(r"(?i)(CERTIFICATE_VERIFY_FAILED|SSL|TLS|x509)\s*(.*)"),
        re.compile(r"(?i)(ECONNREFUSED|ECONNRESET|getaddrinfo ENOTFOUND|connection refused)\s*(.*)"),
    ],
    "memory_resource": [
        re.compile(r"(?i)(out of memory|OOMKilled|exit code 137|heap out of memory)\s*(.*)"),
        re.compile(r"(?i)(No space left on device|resource temporarily unavailable)\s*(.*)"),
    ],
    "caching": [
        re.compile(r"(?i)(cache miss|restore-keys|stale cache|cache corruption)\s*(.*)"),
    ],
    "secrets": [
        re.compile(r"(?i)(Input required and not supplied: token|Permission denied \(publickey\)|token expired)\s*(.*)"),
        re.compile(r"(?i)(secret .+ not available|\.env file not loaded|Vault)\s*(.*)"),
        re.compile(r"(?i)(Secret\s+[A-Z0-9_]+\s+is required, but not provided while calling)\s*(.*)"),
        re.compile(r"(?i)(required, but not provided while calling)\s*(.*)"),
    ],
    "cicd_platform": [
        re.compile(r"(?i)(Invalid workflow file|Resource not accessible by integration|Pipeline filtered out)\s*(.*)"),
        re.compile(r"(?i)(This job is stuck because the project doesn't have any runners|artifact upload)\s*(.*)"),
        re.compile(r"(?i)(workflow_call|actions: none|issues: none|caller workflow|reusable workflow)\s*(.*)"),
    ],
}

EXIT_CODE_PATTERN = re.compile(r"(?:exit code|exited with|return code)[:\s]+(\d+)", re.IGNORECASE)
FILE_LINE_PATTERN = re.compile(r"(?:File|at)\s+[\"']?([^\s\"':]+)[\"']?\s*(?:,\s*line\s+(\d+))?")
STACK_TRACE_PATTERN = re.compile(r"^\s+(at\s+|File\s+|Traceback|\.{3})", re.MULTILINE)
ERROR_LINE_PATTERN = re.compile(r"(?i)^.*(?:error|fail|fatal|exception|critical).*$", re.MULTILINE)
DOCKER_IMAGE_PATTERN = re.compile(
    r"(?i)\b((?:(?:[a-z0-9.-]+(?::\d+)?)/)?(?:[a-z0-9._-]+/)*[a-z0-9._-]+(?::[a-z0-9._-]+))\b"
)
HTTP_STATUS_TEXT_PATTERN = re.compile(
    r"\b([1-5]\d{2})\s+(Unauthorized|Forbidden|Not Found|Too Many Requests|Internal Server Error|Bad Request)\b",
    re.IGNORECASE,
)
DOCKERFILE_LINE_PATTERN = re.compile(r"(?i)Dockerfile:(\d+)")
DOCKER_STAGE_PATTERN = re.compile(r"#(\d+)\s+\[([^\]]+)\]")
DOCKERFILE_SNIPPET_PATTERN = re.compile(r"^\s*(\d+)\s+\|\s+(.+)$", re.MULTILINE)

DOCKER_SUBTYPE_PATTERNS = {
    "registry_auth": [
        re.compile(r"(?i)failed to fetch oauth token"),
        re.compile(r"(?i)failed to authorize"),
        re.compile(r"(?i)401 unauthorized"),
        re.compile(r"(?i)unauthorized: authentication required"),
        re.compile(r"(?i)unauthorized: incorrect"),
        re.compile(r"(?i)pull access denied"),
        re.compile(r"(?i)denied: requested access to the resource is denied"),
    ],
    "image_not_found": [
        re.compile(r"(?i)manifest for .+ not found"),
        re.compile(r"(?i)manifest unknown"),
        re.compile(r"(?i)repository does not exist"),
        re.compile(r"(?i)name unknown"),
    ],
    "build_context_missing": [
        re.compile(r"(?i)copy failed: file not found in build context"),
        re.compile(r"(?i)failed to compute cache key"),
        re.compile(r"(?i)not found: not found"),
    ],
    "rate_limit": [
        re.compile(r"(?i)too many requests"),
        re.compile(r"(?i)toomanyrequests"),
        re.compile(r"(?i)rate limit"),
    ],
    "oom_killed": [
        re.compile(r"(?i)oomkilled"),
        re.compile(r"(?i)exit code 137"),
        re.compile(r"(?i)out of memory"),
    ],
    "port_conflict": [
        re.compile(r"(?i)port is already allocated"),
        re.compile(r"(?i)address already in use"),
        re.compile(r"(?i)bind: address already in use"),
    ],
    "entrypoint_exit": [
        re.compile(r"(?i)executable file not found"),
        re.compile(r"(?i)container .* exited"),
        re.compile(r"(?i)no such file or directory"),
    ],
}

NETWORK_SSL_SUBTYPE_PATTERNS = {
    "k8s_ingress_admission_cert": [
        re.compile(r"(?i)failed calling webhook"),
        re.compile(r"(?i)validate\.nginx\.ingress\.kubernetes\.io"),
        re.compile(r"(?i)nginx-ingress-controller-admission"),
        re.compile(r"(?i)x509:\s*certificate signed by unknown authority"),
    ],
}

WEBHOOK_NAME_PATTERN = re.compile(r'failed calling webhook\s+"([^"]+)"', re.IGNORECASE)
ADMISSION_SERVICE_PATTERN = re.compile(r"https://([a-z0-9.-]+(?:\.[a-z0-9.-]+)*)", re.IGNORECASE)


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
        if any(kw in log.lower() for kw in ["docker", "dockerfile", "container", "daemon:", "manifest unknown", "registry-1.docker.io", "imagepullbackoff"]):
            ecosystems.append("docker")
        if any(kw in log.lower() for kw in ["go build", "go test", ".go"]):
            ecosystems.append("go")
        if any(kw in log.lower() for kw in ["mvn", "gradle", ".java", "pom.xml"]):
            ecosystems.append("java")
        metadata["ecosystems"] = ecosystems

        if "docker" in ecosystems:
            metadata.update(self._extract_docker_metadata(log))

        if any(kw in log.lower() for kw in ["x509", "certificate", "ssl", "tls", "webhook", "ingress"]):
            metadata.update(self._extract_network_ssl_metadata(log))

        return metadata

    def _extract_network_ssl_metadata(self, log: str) -> dict:
        """Extract network/SSL-specific subtype and evidence for prompt grounding."""
        ssl_metadata: dict = {}

        subtype = self._detect_network_ssl_subtype(log)
        if subtype:
            ssl_metadata["network_ssl_subtype"] = subtype

        webhook = WEBHOOK_NAME_PATTERN.search(log)
        if webhook:
            ssl_metadata["webhook_name"] = webhook.group(1)

        svc = ADMISSION_SERVICE_PATTERN.search(log)
        if svc:
            ssl_metadata["failing_service"] = svc.group(1)

        return ssl_metadata

    def _detect_network_ssl_subtype(self, log: str) -> Optional[str]:
        """Detect high-signal network/SSL subtype from log text."""
        for subtype, patterns in NETWORK_SSL_SUBTYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(log):
                    return subtype
        return None

    def _extract_docker_metadata(self, log: str) -> dict:
        """Extract Docker-specific subtype and artifact details."""
        docker_metadata: dict = {}

        subtype = self._detect_docker_subtype(log)
        if subtype:
            docker_metadata["docker_subtype"] = subtype

        images = []
        for match in DOCKER_IMAGE_PATTERN.findall(log):
            image = match.strip()
            if ":" not in image:
                continue
            if image.lower().startswith(("http:", "https:")):
                continue
            if image not in images:
                images.append(image)

        if images:
            docker_metadata["docker_images"] = images[:10]

        registries = []
        for image in images:
            if "/" in image:
                first_part = image.split("/", 1)[0]
                if "." in first_part or ":" in first_part:
                    if first_part not in registries:
                        registries.append(first_part)
        if registries:
            docker_metadata["docker_registries"] = registries[:10]

        http_statuses = []
        for code, text in HTTP_STATUS_TEXT_PATTERN.findall(log):
            item = f"{code} {text}"
            if item not in http_statuses:
                http_statuses.append(item)
        if http_statuses:
            docker_metadata["http_statuses"] = http_statuses[:10]

        stage_matches = DOCKER_STAGE_PATTERN.findall(log)
        if stage_matches:
            docker_metadata["docker_build_stages"] = [
                {"step": step, "name": name.strip()} for step, name in stage_matches[:10]
            ]

        dockerfile_line_match = DOCKERFILE_LINE_PATTERN.search(log)
        if dockerfile_line_match:
            dockerfile_line = int(dockerfile_line_match.group(1))
            docker_metadata["dockerfile_line"] = dockerfile_line

            snippet_lines = {
                int(line_no): content.strip()
                for line_no, content in DOCKERFILE_SNIPPET_PATTERN.findall(log)
            }
            if dockerfile_line in snippet_lines:
                docker_metadata["failing_instruction"] = snippet_lines[dockerfile_line]

        if "docker.io" in log.lower() and not registries:
            docker_metadata["docker_registries"] = ["docker.io"]

        return docker_metadata

    def _detect_docker_subtype(self, log: str) -> Optional[str]:
        """Detect a more precise Docker/container failure subtype."""
        for subtype, patterns in DOCKER_SUBTYPE_PATTERNS.items():
            if any(pattern.search(log) for pattern in patterns):
                return subtype
        return None
