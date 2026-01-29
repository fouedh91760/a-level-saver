"""
PyBars3-based Handlebars renderer.

This module provides a drop-in replacement for the regex-based Handlebars
parsing in TemplateEngine. It uses pybars3 library for robust template
rendering with proper support for nested blocks, partials, and helpers.

Architecture:
- PybarsRenderer loads and compiles all partials at initialization
- Templates are compiled once and cached by content hash
- Context is prepared to handle None values (converted to empty strings)
- Supports: {{variable}}, {{> partial}}, {{#if}}, {{#unless}}, {{#each}}
"""
import logging
import re
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from pybars import Compiler

logger = logging.getLogger(__name__)


class PybarsRenderer:
    """
    Renders Handlebars templates using pybars3.

    This class provides a clean, library-based implementation of Handlebars
    template rendering to replace the fragile regex-based implementation.
    """

    def __init__(self, states_path: Path):
        """
        Initialize the renderer.

        Args:
            states_path: Path to the states directory containing templates
        """
        self.states_path = states_path
        self.compiler = Compiler()
        self._compiled_cache: Dict[int, Callable] = {}
        self._partials: Dict[str, Callable] = {}
        self._partial_sources: Dict[str, str] = {}  # For debugging

    def load_all_partials(self) -> int:
        """
        Pre-load and compile all partials from the templates directory.

        Returns:
            Number of partials loaded successfully
        """
        count = 0

        # 1. HTML partials (new modular system) - under templates/partials/
        partials_root = self.states_path / "templates" / "partials"
        if partials_root.exists():
            for partial_file in partials_root.rglob("*.html"):
                # Create partial name from relative path
                # e.g., partials/intentions/statut_dossier.html -> partials/intentions/statut_dossier
                relative = partial_file.relative_to(self.states_path / "templates")
                partial_name = str(relative.with_suffix('')).replace('\\', '/')
                if self._register_partial(partial_name, partial_file):
                    count += 1

        # 2. MD blocks (legacy system) - under blocks/
        blocks_path = self.states_path / "blocks"
        if blocks_path.exists():
            for block_file in blocks_path.glob("*.md"):
                # Block name is just the filename without extension
                partial_name = block_file.stem
                if self._register_partial(partial_name, block_file):
                    count += 1

        # 3. HTML templates in base_legacy (for backwards compatibility)
        base_legacy_path = self.states_path / "templates" / "base_legacy"
        if base_legacy_path.exists():
            for template_file in base_legacy_path.glob("*.html"):
                partial_name = f"base_legacy/{template_file.stem}"
                if self._register_partial(partial_name, template_file):
                    count += 1

        logger.info(f"PybarsRenderer: Loaded {count} partials")
        return count

    def _register_partial(self, name: str, file_path: Path) -> bool:
        """
        Load, clean, and compile a partial.

        Args:
            name: The partial name (used in {{> name}})
            file_path: Path to the partial file

        Returns:
            True if partial was successfully registered
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            content = self._clean_content(content)

            # Store source for debugging
            self._partial_sources[name] = content

            # Compile the partial
            self._partials[name] = self.compiler.compile(content)
            return True

        except Exception as e:
            logger.warning(f"Failed to compile partial '{name}' from {file_path}: {e}")
            return False

    def _clean_content(self, content: str) -> str:
        """
        Remove comments and normalize content for pybars3.

        Args:
            content: Raw template content

        Returns:
            Cleaned content ready for compilation
        """
        # Remove Handlebars comments {{!-- ... --}}
        content = re.sub(r'\{\{!--.*?--\}\}', '', content, flags=re.DOTALL)

        # Remove HTML comments <!-- ... -->
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # Don't strip - preserve the content structure
        return content

    def _prepare_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare context for pybars3 rendering.

        - Converts None values to empty strings (pybars3 doesn't handle None well)
        - Recursively processes nested dicts and lists

        Args:
            context: The original template context

        Returns:
            Prepared context safe for pybars3
        """
        if context is None:
            return {}

        result = {}
        for key, value in context.items():
            if value is None:
                result[key] = ''
            elif isinstance(value, dict):
                result[key] = self._prepare_context(value)
            elif isinstance(value, list):
                result[key] = [
                    self._prepare_context(item) if isinstance(item, dict)
                    else ('' if item is None else item)
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def render(self, template_content: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.

        Args:
            template_content: The Handlebars template string
            context: Data to render into the template

        Returns:
            Rendered template string
        """
        # Clean the template content
        cleaned = self._clean_content(template_content)

        # Compile with caching (by content hash)
        template_hash = hash(cleaned)
        if template_hash not in self._compiled_cache:
            try:
                self._compiled_cache[template_hash] = self.compiler.compile(cleaned)
            except Exception as e:
                logger.error(f"Failed to compile template: {e}")
                logger.debug(f"Template content:\n{cleaned[:500]}...")
                # Return template as-is if compilation fails
                return template_content

        template = self._compiled_cache[template_hash]

        # Prepare context (handle None values)
        prepared_context = self._prepare_context(context)

        # Render with partials
        try:
            result = template(prepared_context, partials=self._partials)
            return result
        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            logger.debug(f"Context keys: {list(prepared_context.keys())}")
            # Return cleaned template as fallback
            return cleaned

    def get_partial(self, name: str) -> Optional[str]:
        """
        Get the source of a registered partial (for debugging).

        Args:
            name: Partial name

        Returns:
            Partial source or None if not found
        """
        return self._partial_sources.get(name)

    def list_partials(self) -> list:
        """
        List all registered partial names.

        Returns:
            List of partial names
        """
        return sorted(self._partials.keys())
