"""
Edge Layer: Preprocessor
Text cleaning and normalization for CI/CD logs.
"""

import re
from typing import Optional


class LogPreprocessor:
    """Cleans and normalizes raw CI/CD log text for downstream processing."""

    # Patterns to strip from logs
    TIMESTAMP_PATTERN = re.compile(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*"
    )
    ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")
    GH_ACTIONS_PREFIX = re.compile(r"^##\[(?:group|endgroup|command|debug|warning)\]", re.MULTILINE)
    PROGRESS_BAR = re.compile(r"[\|/\-\\]{2,}|\[=+>?\s*\]|\d+%\|[█▓░ ]+\|")
    BLANK_LINES = re.compile(r"\n{3,}")
    WHITESPACE_RUNS = re.compile(r"[ \t]{4,}")

    def preprocess(
        self,
        raw_log: str,
        strip_timestamps: bool = True,
        strip_ansi: bool = True,
        strip_progress: bool = True,
        max_lines: Optional[int] = None,
    ) -> str:
        """Clean and normalize a raw CI/CD log string.

        Args:
            raw_log: The raw log text.
            strip_timestamps: Remove timestamp prefixes.
            strip_ansi: Remove ANSI escape codes (colors).
            strip_progress: Remove progress bars and spinners.
            max_lines: If set, truncate to this many lines.

        Returns:
            Cleaned log string.
        """
        text = raw_log

        if strip_ansi:
            text = self.ANSI_ESCAPE.sub("", text)

        if strip_timestamps:
            text = self.TIMESTAMP_PATTERN.sub("", text)

        if strip_progress:
            text = self.PROGRESS_BAR.sub("", text)

        # Remove GitHub Actions control prefixes
        text = self.GH_ACTIONS_PREFIX.sub("", text)

        # Collapse excessive blank lines
        text = self.BLANK_LINES.sub("\n\n", text)

        # Collapse long whitespace runs (but preserve indentation up to 4 spaces)
        text = self.WHITESPACE_RUNS.sub("    ", text)

        # Strip each line
        lines = [line.rstrip() for line in text.split("\n")]

        # Remove empty leading/trailing lines
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        if max_lines and len(lines) > max_lines:
            # Keep first half and last half to preserve both early context and final errors
            half = max_lines // 2
            lines = lines[:half] + ["... [TRUNCATED] ..."] + lines[-half:]

        return "\n".join(lines)

    def extract_error_section(self, log: str, window: int = 30) -> str:
        """Extract the most relevant error section from a log.

        Finds lines with error keywords and returns surrounding context.

        Args:
            log: Preprocessed log text.
            window: Number of context lines around error.

        Returns:
            The extracted error section.
        """
        lines = log.split("\n")
        error_keywords = re.compile(
            r"(?i)(error|fail|fatal|exception|critical|panic|abort)", re.IGNORECASE
        )

        # Find the last significant error line (usually most relevant)
        error_idx = None
        for i in range(len(lines) - 1, -1, -1):
            if error_keywords.search(lines[i]) and len(lines[i].strip()) > 10:
                error_idx = i
                break

        if error_idx is None:
            # No error found; return last N lines
            return "\n".join(lines[-window:])

        start = max(0, error_idx - window // 2)
        end = min(len(lines), error_idx + window // 2 + 1)
        return "\n".join(lines[start:end])
