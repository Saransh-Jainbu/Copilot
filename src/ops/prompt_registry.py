"""
Ops: Prompt Registry
Manages versioned prompt templates for the LLM agent.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """A versioned prompt template."""
    version: str
    author: str
    description: str
    category: str
    content: str
    file_path: str


class PromptRegistry:
    """Manages versioned prompt templates.

    Loads prompts from the prompts directory, supports version selection,
    and provides A/B testing utilities.
    """

    def __init__(self, prompts_dir: str = "src/cloud/prompts"):
        self.prompts_dir = prompts_dir
        self._prompts: dict[str, PromptTemplate] = {}
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load all prompt templates from the prompts directory."""
        if not os.path.exists(self.prompts_dir):
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        for filename in os.listdir(self.prompts_dir):
            if filename.endswith(".txt"):
                filepath = os.path.join(self.prompts_dir, filename)
                template = self._parse_prompt_file(filepath)
                if template:
                    key = f"{template.category}:{template.version}"
                    self._prompts[key] = template
                    logger.debug(f"Loaded prompt: {key}")

        logger.info(f"Loaded {len(self._prompts)} prompt templates")

    def _parse_prompt_file(self, filepath: str) -> Optional[PromptTemplate]:
        """Parse a prompt file with metadata headers."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse metadata from comment headers
            metadata = {}
            lines = content.split("\n")
            content_start = 0
            for i, line in enumerate(lines):
                match = re.match(r"^#\s*(\w+):\s*(.+)$", line)
                if match:
                    metadata[match.group(1).lower()] = match.group(2).strip()
                    content_start = i + 1
                elif line.strip() == "":
                    content_start = i + 1
                else:
                    break

            prompt_content = "\n".join(lines[content_start:]).strip()

            return PromptTemplate(
                version=metadata.get("version", "v1"),
                author=metadata.get("author", "unknown"),
                description=metadata.get("description", ""),
                category=metadata.get("category", os.path.splitext(os.path.basename(filepath))[0]),
                content=prompt_content,
                file_path=filepath,
            )

        except Exception as e:
            logger.error(f"Failed to parse prompt file {filepath}: {e}")
            return None

    def get(self, category: str, version: str = "v1") -> Optional[PromptTemplate]:
        """Get a prompt template by category and version.

        Args:
            category: The prompt category (e.g., 'diagnosis', 'classification').
            version: The version string (e.g., 'v1').

        Returns:
            PromptTemplate or None if not found.
        """
        key = f"{category}:{version}"
        return self._prompts.get(key)

    def list_prompts(self) -> list[dict]:
        """List all available prompt templates."""
        return [
            {
                "key": key,
                "version": t.version,
                "category": t.category,
                "description": t.description,
            }
            for key, t in self._prompts.items()
        ]

    def get_versions(self, category: str) -> list[str]:
        """Get all available versions for a category."""
        return [
            t.version
            for key, t in self._prompts.items()
            if t.category == category
        ]
