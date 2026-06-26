"""PromptLoader — Centralized prompt template loading utility.

Loads prompt templates from the /prompts directory, supporting
variable substitution via Python str.format_map().
"""

import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("VentureMind.PromptLoader")

# Default prompts directory relative to the project root
_DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class PromptLoader:
    """Loads and caches prompt templates from disk with variable substitution support.

    Usage:
        loader = PromptLoader()
        prompt = loader.render("market_analysis", industry="Enterprise AI", startup_name="Acme")
    """

    def __init__(self, prompts_dir: str | Path | None = None):
        """Initialize the loader with a directory containing .txt prompt templates.

        Args:
            prompts_dir: Absolute or relative path to the prompts directory.
                         Defaults to the project's /prompts folder.
        """
        self.prompts_dir = Path(prompts_dir) if prompts_dir else _DEFAULT_PROMPTS_DIR
        if not self.prompts_dir.is_dir():
            logger.warning(
                f"Prompts directory does not exist: {self.prompts_dir}. "
                "Templates will not be loadable until the directory is created."
            )
        self._cache: dict[str, str] = {}

    def _load_template(self, name: str) -> str:
        """Load a template file by name (without extension) from the prompts directory.

        The template is cached in-memory after the first load.

        Args:
            name: Template name (e.g. 'market_analysis' loads 'market_analysis.txt').

        Returns:
            The raw template string.

        Raises:
            FileNotFoundError: If the template file does not exist.
        """
        if name in self._cache:
            return self._cache[name]

        filepath = self.prompts_dir / f"{name}.txt"
        if not filepath.is_file():
            raise FileNotFoundError(
                f"Prompt template '{name}' not found at: {filepath}"
            )

        template_text = filepath.read_text(encoding="utf-8")
        self._cache[name] = template_text
        logger.debug(f"Loaded prompt template: {name} ({len(template_text)} chars)")
        return template_text

    def render(self, name: str, **variables) -> str:
        """Load a prompt template and substitute variables using str.format_map().

        Variables in the template should be written as {variable_name}.
        Any unmatched placeholders are left as-is (no KeyError raised).

        Args:
            name: Template name (e.g. 'market_analysis').
            **variables: Key-value pairs to substitute into the template.

        Returns:
            The rendered prompt string with variables replaced.
        """
        template = self._load_template(name)
        # Use a defaultdict-like approach: unmatched keys stay as {key}
        safe_vars = _SafeFormatDict(variables)
        try:
            return template.format_map(safe_vars)
        except Exception as e:
            logger.warning(f"Failed to render template '{name}': {e}. Returning raw template.")
            return template

    def list_templates(self) -> list[str]:
        """List all available template names in the prompts directory.

        Returns:
            Sorted list of template names (without .txt extension).
        """
        if not self.prompts_dir.is_dir():
            return []
        return sorted(
            p.stem for p in self.prompts_dir.glob("*.txt") if p.is_file()
        )

    def clear_cache(self) -> None:
        """Clear the in-memory template cache, forcing fresh reads on next access."""
        self._cache.clear()


class _SafeFormatDict(dict):
    """Dict subclass that returns the original {key} placeholder for missing keys,
    preventing KeyError during str.format_map() calls."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


@lru_cache
def get_prompt_loader(prompts_dir: str | None = None) -> PromptLoader:
    """Cached factory for the singleton PromptLoader instance.

    Args:
        prompts_dir: Optional custom prompts directory path.

    Returns:
        A PromptLoader instance.
    """
    return PromptLoader(prompts_dir=prompts_dir)
