"""AST parsing engine backed by tree-sitter (with graceful fallback)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from regulatory_agent_kit.exceptions import ASTError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import tree-sitter; provide stubs if unavailable
# ---------------------------------------------------------------------------

_TREE_SITTER_AVAILABLE = False

try:
    import tree_sitter

    _TREE_SITTER_AVAILABLE = True
except ImportError:
    logger.info("tree-sitter not available — AST features will be limited")

try:
    import tree_sitter_languages  # type: ignore[import-not-found]

    _LANGUAGES_AVAILABLE = True
except ImportError:
    tree_sitter_languages = None
    _LANGUAGES_AVAILABLE = False
    logger.info("tree-sitter-languages not available — language auto-loading disabled")


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".kt": "kotlin",
    ".scala": "scala",
    ".swift": "swift",
}


# ---------------------------------------------------------------------------
# Node range helper (works with or without tree-sitter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeRange:
    """Start/end position of a syntax node."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int


# ---------------------------------------------------------------------------
# AST Engine
# ---------------------------------------------------------------------------


@dataclass
class ASTEngine:
    """Parse source code and query its AST via tree-sitter.

    If tree-sitter is not installed the engine raises ``ASTError`` on parse
    attempts rather than crashing at import time.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, source: str | bytes, language: str) -> Any:
        """Parse *source* and return the tree-sitter ``Tree``.

        Raises:
            ASTError: When tree-sitter is unavailable or parsing fails.
        """
        parser = self._get_parser(language)
        if isinstance(source, str):
            source = source.encode("utf-8")
        tree: Any = parser.parse(source)
        return tree

    def find_classes(self, tree: Any) -> list[Any]:
        """Return all class-definition nodes in *tree*."""
        return self._collect_by_type(tree.root_node, {"class_definition", "class_declaration"})

    def find_methods(self, tree: Any) -> list[Any]:
        """Return all method/function-definition nodes in *tree*."""
        return self._collect_by_type(
            tree.root_node,
            {"function_definition", "method_declaration", "method_definition"},
        )

    def find_annotations(self, tree: Any) -> list[Any]:
        """Return all annotation/decorator nodes in *tree*."""
        return self._collect_by_type(
            tree.root_node,
            {"decorator", "annotation", "marker_annotation"},
        )

    def get_node_range(self, node: Any) -> NodeRange:
        """Extract the line/column range of a syntax *node*."""
        return NodeRange(
            start_line=node.start_point[0],
            start_column=node.start_point[1],
            end_line=node.end_point[0],
            end_column=node.end_point[1],
        )

    def check_implements(self, tree: Any, interface_name: str) -> bool:
        """Return ``True`` if any class in *tree* implements *interface_name*.

        Uses a simple heuristic: checks whether the interface name appears
        in the superclass list of any class node.
        """
        for cls_node in self.find_classes(tree):
            if self._superclass_contains(cls_node, interface_name):
                return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_tree_sitter(self) -> None:
        if not _TREE_SITTER_AVAILABLE:
            msg = "tree-sitter is not installed — cannot parse AST"
            raise ASTError(msg)

    def _get_parser(self, language: str) -> Any:
        """Build a tree-sitter Parser for *language*."""
        self._require_tree_sitter()

        if not _LANGUAGES_AVAILABLE:
            msg = "tree-sitter-languages is not installed — cannot auto-load language grammars"
            raise ASTError(msg)

        try:
            lang_obj = tree_sitter_languages.get_language(language)
        except Exception as exc:
            msg = f"Failed to load tree-sitter grammar for '{language}': {exc}"
            raise ASTError(msg) from exc

        parser = tree_sitter.Parser()
        parser.language = lang_obj
        return parser

    @staticmethod
    def _collect_by_type(node: Any, type_names: set[str]) -> list[Any]:
        """Walk *node* recursively and collect nodes whose type is in *type_names*."""
        results: list[Any] = []

        def _walk(n: Any) -> None:
            if n.type in type_names:
                results.append(n)
            for child in n.children:
                _walk(child)

        _walk(node)
        return results

    @staticmethod
    def _superclass_contains(cls_node: Any, name: str) -> bool:
        """Check if *cls_node* inherits from *name* (text-based heuristic)."""
        for child in cls_node.children:
            if child.type in ("superclass", "argument_list", "superclasses", "super_interfaces"):
                text = child.text.decode("utf-8") if isinstance(child.text, bytes) else child.text
                if name in text:
                    return True
        return False


def _detect_language(file_path: str | Path) -> str:
    """Detect programming language from a file extension.

    Raises:
        ASTError: When the extension is not recognised.
    """
    ext = Path(file_path).suffix.lower()
    lang = _EXTENSION_MAP.get(ext)
    if lang is None:
        msg = f"Unsupported file extension for AST parsing: {ext}"
        raise ASTError(msg)
    return lang
