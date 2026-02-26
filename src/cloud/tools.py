"""
Cloud Layer: Agent Tools
Tool definitions for the LangChain/LangGraph agent.
These are callable tools the agent can invoke during reasoning.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentTools:
    """Collection of tools available to the debugging agent.

    Each tool is a callable that the agent can invoke during its reasoning loop.
    """

    def __init__(self, classifier=None, retriever=None):
        self.classifier = classifier
        self.retriever = retriever

    def get_tools(self) -> list[dict]:
        """Return tool definitions in a format suitable for LLM tool-calling."""
        return [
            {
                "name": "classify_error",
                "description": (
                    "Classify a CI/CD log into a failure category. "
                    "Returns: category, confidence, reasoning."
                ),
                "function": self.classify_error,
            },
            {
                "name": "search_docs",
                "description": (
                    "Search documentation and past errors for relevant context. "
                    "Input: a natural language query about the error."
                ),
                "function": self.search_docs,
            },
            {
                "name": "analyze_stack_trace",
                "description": (
                    "Parse and analyze a stack trace to identify the root cause "
                    "location (file, line, function)."
                ),
                "function": self.analyze_stack_trace,
            },
        ]

    def classify_error(self, log_text: str) -> dict[str, Any]:
        """Classify a CI/CD failure log."""
        if not self.classifier:
            return {"error": "Classifier not configured"}
        result = self.classifier.classify(log_text)
        return result.to_dict()

    def search_docs(self, query: str) -> str:
        """Search documentation for relevant context."""
        if not self.retriever:
            return "Retriever not configured"
        result = self.retriever.retrieve(query)
        return result.to_context_string()

    def analyze_stack_trace(self, stack_trace: str) -> dict[str, Any]:
        """Analyze a stack trace to extract key information."""
        from src.edge.log_parser import LogParser
        parser = LogParser()
        parsed = parser.parse(stack_trace)
        return {
            "file_path": parsed.file_path,
            "line_number": parsed.line_number,
            "error_type": parsed.error_type,
            "error_message": parsed.error_message,
            "stack_frames": parsed.stack_trace[:10],
        }
