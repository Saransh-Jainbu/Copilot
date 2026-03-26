"""
Ops: Agent Logger
Structured logging for agent steps, tool calls, and reasoning traces.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AgentLogger:
    """Structured logger for agent activity.

    Logs every step of the agent's reasoning to a JSON audit trail.
    Supports file-based and in-memory logging.
    """

    def __init__(self, log_dir: str = "logs/agent", enable_file: bool = True):
        self.log_dir = log_dir
        self.enable_file = enable_file
        self._session_id: Optional[str] = None
        self._events: list[dict] = []

        if enable_file:
            os.makedirs(log_dir, exist_ok=True)

    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new logging session.

        Args:
            session_id: Optional custom session ID.

        Returns:
            The session ID.
        """
        self._session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self._events = []
        self._log_event("session_start", {"session_id": self._session_id})
        return self._session_id

    def log_step(
        self,
        step_number: int,
        action: str,
        input_data: Any,
        output_data: Any,
        latency_ms: int,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log a single agent reasoning step.

        Args:
            step_number: Sequential step number.
            action: Action taken (classify, retrieve, reason, etc.).
            input_data: Input to the step (will be truncated).
            output_data: Output from the step (will be truncated).
            latency_ms: Step latency in ms.
            metadata: Additional metadata.
        """
        self._log_event("agent_step", {
            "step": step_number,
            "action": action,
            "input": self._truncate(input_data),
            "output": self._truncate(output_data),
            "latency_ms": latency_ms,
            **(metadata or {}),
        })

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        latency_ms: int,
    ) -> None:
        """Log a tool invocation."""
        self._log_event("tool_call", {
            "tool": tool_name,
            "input": self._truncate(tool_input),
            "output": self._truncate(tool_output),
            "latency_ms": latency_ms,
        })

    def log_error(self, error: str, context: Optional[dict] = None) -> None:
        """Log an error."""
        self._log_event("error", {
            "error": error,
            **(context or {}),
        })

    def end_session(self, summary: Optional[dict] = None) -> list[dict]:
        """End the logging session and return all events.

        Args:
            summary: Optional session summary dict.

        Returns:
            All logged events for the session.
        """
        self._log_event("session_end", summary or {})

        if self.enable_file and self._session_id:
            self._save_to_file()

        return self._events

    def _log_event(self, event_type: str, data: dict) -> None:
        """Internal: create and store a log event."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "event_type": event_type,
            **data,
        }
        self._events.append(event)
        logger.debug(f"Agent event: {event_type} | {json.dumps(data)[:200]}")

    def _save_to_file(self) -> None:
        """Save session events to a JSON file."""
        filepath = os.path.join(self.log_dir, f"{self._session_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._events, f, indent=2, default=str)
            logger.info(f"Saved agent log to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save agent log: {e}")

    def _truncate(self, data: Any, max_length: int = 500) -> Any:
        """Truncate data for storage."""
        if isinstance(data, str) and len(data) > max_length:
            return data[:max_length] + f"... [truncated, total: {len(data)}]"
        if isinstance(data, dict):
            return {k: self._truncate(v, max_length) for k, v in data.items()}
        return data
