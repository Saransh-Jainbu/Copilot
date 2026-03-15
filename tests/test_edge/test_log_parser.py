"""
Tests for Edge Layer: Log Parser
"""

import pytest
from src.edge.log_parser import LogParser, ParsedLog


@pytest.fixture
def parser():
    return LogParser()


class TestLogParser:
    """Test suite for the CI/CD log parser."""

    def test_parse_python_import_error(self, parser):
        log = """
        Traceback (most recent call last):
          File "app.py", line 3, in <module>
            import numpy as np
        ModuleNotFoundError: No module named 'numpy'
        ##[error]Process completed with exit code 1.
        """
        result = parser.parse(log)
        assert result.error_type == "dependency_error"
        assert "numpy" in result.error_message.lower()
        assert result.exit_code == 1

    def test_parse_npm_dependency_error(self, parser):
        log = """
        npm ERR! code ERESOLVE
        npm ERR! ERESOLVE unable to resolve dependency tree
        npm ERR! Could not resolve dependency:
        npm ERR! peer react@"^17.0.0" from some-library@2.1.0
        ##[error]Process completed with exit code 1.
        """
        result = parser.parse(log)
        assert result.error_type == "dependency_error"

    def test_parse_syntax_error(self, parser):
        log = """
        File "main.py", line 42
            print(hello world)
                        ^
        SyntaxError: invalid syntax
        """
        result = parser.parse(log)
        assert result.error_type == "syntax_error"
        assert result.file_path == "main.py"
        assert result.line_number == 42

    def test_parse_build_failure(self, parser):
        log = """
        Step 5/10 : RUN make build
        make: *** [Makefile:25: all] Error 2
        build failed with errors
        The command returned a non-zero code: 2
        ##[error]Docker build failed with exit code 1.
        """
        result = parser.parse(log)
        assert result.error_type == "build_failure"

    def test_parse_test_failure(self, parser):
        log = """
        FAILED tests/test_auth.py::test_login - AssertionError: Expected 200, got 401
        FAILED tests/test_api.py::test_delete - AssertionError: assert 204 == 403
        2 failed, 3 passed in 4.52s
        ##[error]Process completed with exit code 1.
        """
        result = parser.parse(log)
        assert result.error_type == "test_failure"
        assert result.exit_code == 1

    def test_parse_timeout(self, parser):
        log = """
        Error: operation timed out after 300 seconds
        The job exceeded the maximum time limit.
        ##[error]The operation was canceled.
        """
        result = parser.parse(log)
        assert result.error_type == "timeout"

    def test_parse_permission_error(self, parser):
        log = """
        PermissionError: [Errno 13] Permission denied: '/usr/local/lib/python3.9'
        Consider using the --user option.
        ##[error]Process completed with exit code 1.
        """
        result = parser.parse(log)
        assert result.error_type == "permission_error"
        assert result.exit_code == 1

    def test_parse_unknown_error(self, parser):
        log = "Some random log output with no error patterns."
        result = parser.parse(log)
        assert result.error_type == "unknown"

    def test_parse_docker_registry_auth_subtype(self, parser):
        log = """
        #3 [internal] load metadata for docker.io/library/node:18-alpine
        #3 ERROR: failed to authorize: rpc error: code = Unknown desc = failed to fetch oauth token:
        unexpected status: 401 Unauthorized
        ERROR: failed to solve: node:18-alpine: failed to resolve source metadata
        """
        result = parser.parse(log)
        assert result.error_type == "docker_container"
        assert result.metadata["docker_subtype"] == "registry_auth"
        assert "node:18-alpine" in result.metadata["docker_images"]
        assert "docker.io" in result.metadata["docker_registries"]
        assert "401 Unauthorized" in result.metadata["http_statuses"]

    def test_parse_docker_instruction_evidence(self, parser):
        log = """
        #3 [internal] load metadata for docker.io/library/node:18-alpine
        Dockerfile:1
           1 | FROM node:18-alpine
           2 | WORKDIR /app
        """
        result = parser.parse(log)
        assert result.metadata["dockerfile_line"] == 1
        assert result.metadata["failing_instruction"] == "FROM node:18-alpine"

    def test_extract_stack_trace(self, parser):
        log = """
        Traceback (most recent call last):
          File "app.py", line 10, in main
            result = process()
          File "utils.py", line 5, in process
            return 1 / 0
        ZeroDivisionError: division by zero
        """
        result = parser.parse(log)
        assert len(result.stack_trace) >= 3

    def test_extract_metadata_github_actions(self, parser):
        log = """
        ##[group]Run pip install
        ##[command]pip install -r requirements.txt
        ##[error]Process completed with exit code 1.
        """
        result = parser.parse(log)
        assert result.metadata["platform"] == "github_actions"

    def test_extract_metadata_ecosystems(self, parser):
        log = """
        pip install numpy failed
        npm ERR! missing dependency
        docker build failed
        """
        result = parser.parse(log)
        assert "python" in result.metadata["ecosystems"]
        assert "nodejs" in result.metadata["ecosystems"]
        assert "docker" in result.metadata["ecosystems"]

    def test_to_dict(self, parser):
        log = "ModuleNotFoundError: No module named 'flask'"
        result = parser.parse(log)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "error_type" in d
        assert "error_message" in d
        assert "metadata" in d
