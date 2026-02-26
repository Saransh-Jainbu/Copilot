"""
Tests for Edge Layer: Log Preprocessor
"""

import pytest
from src.edge.preprocessor import LogPreprocessor


@pytest.fixture
def preprocessor():
    return LogPreprocessor()


class TestLogPreprocessor:
    """Test suite for the CI/CD log preprocessor."""

    def test_strip_ansi_codes(self, preprocessor):
        log = "\x1b[31mERROR:\x1b[0m Something failed\n\x1b[32mOK\x1b[0m done"
        result = preprocessor.preprocess(log, strip_timestamps=False)
        assert "\x1b[" not in result
        assert "ERROR: Something failed" in result
        assert "OK done" in result

    def test_strip_timestamps(self, preprocessor):
        log = (
            "2024-06-15T10:30:45Z Installing dependencies\n"
            "2024-06-15 10:30:46 Running tests\n"
            "2024-06-15T10:30:47+05:30 Build complete"
        )
        result = preprocessor.preprocess(log, strip_ansi=False)
        assert "2024-06-15" not in result
        assert "Installing dependencies" in result
        assert "Running tests" in result
        assert "Build complete" in result

    def test_strip_progress_bars(self, preprocessor):
        log = (
            "Downloading packages\n"
            "50%|█████     | 50/100\n"
            "[===>      ]\n"
            "Done"
        )
        result = preprocessor.preprocess(
            log, strip_timestamps=False, strip_ansi=False
        )
        assert "Downloading packages" in result
        assert "Done" in result

    def test_strip_github_actions_prefixes(self, preprocessor):
        log = (
            "##[group]Run pip install\n"
            "pip install -r requirements.txt\n"
            "##[command]pip install flask\n"
            "##[endgroup]\n"
            "##[error]Process completed with exit code 1."
        )
        result = preprocessor.preprocess(
            log, strip_timestamps=False, strip_ansi=False
        )
        # ##[group], ##[command], ##[endgroup] should be stripped
        assert "##[group]" not in result
        assert "##[command]" not in result
        assert "##[endgroup]" not in result
        # ##[error] is NOT in the strip list (it's important), so it stays
        assert "##[error]" in result
        # Actual content should remain
        assert "pip install -r requirements.txt" in result

    def test_collapse_blank_lines(self, preprocessor):
        log = "Line 1\n\n\n\n\nLine 2\n\n\n\n\nLine 3"
        result = preprocessor.preprocess(
            log, strip_timestamps=False, strip_ansi=False, strip_progress=False
        )
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_max_lines_truncation(self, preprocessor):
        lines = [f"Log line {i}" for i in range(100)]
        log = "\n".join(lines)
        result = preprocessor.preprocess(
            log, strip_timestamps=False, strip_ansi=False, max_lines=20
        )
        result_lines = result.split("\n")
        # Should be truncated to ~20 lines + 1 truncation marker
        assert len(result_lines) <= 22
        assert "TRUNCATED" in result
        # Should keep first and last portions
        assert "Log line 0" in result
        assert "Log line 99" in result

    def test_no_strip_options(self, preprocessor):
        log = "2024-01-01T00:00:00Z \x1b[31mError\x1b[0m 50%|█████|"
        result = preprocessor.preprocess(
            log,
            strip_timestamps=False,
            strip_ansi=False,
            strip_progress=False,
        )
        # All original content should be preserved (except whitespace cleanup)
        assert "2024-01-01" in result
        assert "\x1b[31m" in result

    def test_extract_error_section_finds_error(self, preprocessor):
        lines = [f"Normal log line {i}" for i in range(20)]
        lines.insert(15, "FATAL ERROR: Out of memory")
        log = "\n".join(lines)
        result = preprocessor.extract_error_section(log, window=6)
        assert "FATAL ERROR: Out of memory" in result
        # Should include surrounding context
        result_lines = result.split("\n")
        assert len(result_lines) <= 7  # window of 6 + 1

    def test_extract_error_section_no_error(self, preprocessor):
        lines = [f"All good {i}" for i in range(50)]
        log = "\n".join(lines)
        result = preprocessor.extract_error_section(log, window=10)
        # Should return last N lines as fallback
        assert "All good 49" in result
        assert "All good 40" in result

    def test_full_preprocessing_pipeline(self, preprocessor):
        """End-to-end test with a realistic CI/CD log."""
        log = (
            "2024-06-15T10:30:00Z ##[group]Run pip install\n"
            "2024-06-15T10:30:01Z \x1b[32m+ pip install -r requirements.txt\x1b[0m\n"
            "2024-06-15T10:30:02Z Collecting flask==3.0.0\n"
            "2024-06-15T10:30:02Z 50%|█████     |\n"
            "\n\n\n\n\n"
            "2024-06-15T10:30:05Z ERROR: Could not find version that satisfies\n"
            "2024-06-15T10:30:05Z ##[error]Process completed with exit code 1.\n"
        )
        result = preprocessor.preprocess(log)
        # Timestamps stripped
        assert "2024-06-15" not in result
        # ANSI stripped
        assert "\x1b[" not in result
        # GH Actions prefix stripped
        assert "##[group]" not in result
        # Blank lines collapsed
        assert "\n\n\n" not in result
        # Important content preserved
        assert "pip install -r requirements.txt" in result
        assert "ERROR: Could not find version that satisfies" in result
        assert "##[error]" in result
