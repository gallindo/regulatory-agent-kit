"""Tests for ASTEngine (Phase 7)."""

from __future__ import annotations

import pytest

from regulatory_agent_kit.exceptions import ASTError
from regulatory_agent_kit.tools.ast_engine import ASTEngine, NodeRange, _detect_language

# ======================================================================
# Language detection
# ======================================================================


class TestDetectLanguage:
    """Test _detect_language from file extensions."""

    def test_python_extension(self) -> None:
        assert _detect_language("foo/bar.py") == "python"

    def test_java_extension(self) -> None:
        assert _detect_language("Foo.java") == "java"

    def test_javascript_extension(self) -> None:
        assert _detect_language("index.js") == "javascript"

    def test_typescript_extension(self) -> None:
        assert _detect_language("app.ts") == "typescript"

    def test_go_extension(self) -> None:
        assert _detect_language("main.go") == "go"

    def test_unsupported_extension_raises(self) -> None:
        with pytest.raises(ASTError, match="Unsupported"):
            _detect_language("data.xyz")


# ======================================================================
# ASTEngine class structure
# ======================================================================


class TestASTEngine:
    """Verify ASTEngine has the expected public interface."""

    def test_has_parse_method(self) -> None:
        engine = ASTEngine()
        assert callable(getattr(engine, "parse", None))

    def test_has_find_classes(self) -> None:
        engine = ASTEngine()
        assert callable(getattr(engine, "find_classes", None))

    def test_has_find_methods(self) -> None:
        engine = ASTEngine()
        assert callable(getattr(engine, "find_methods", None))

    def test_has_find_annotations(self) -> None:
        engine = ASTEngine()
        assert callable(getattr(engine, "find_annotations", None))

    def test_has_get_node_range(self) -> None:
        engine = ASTEngine()
        assert callable(getattr(engine, "get_node_range", None))

    def test_has_check_implements(self) -> None:
        engine = ASTEngine()
        assert callable(getattr(engine, "check_implements", None))

    def test_node_range_dataclass(self) -> None:
        nr = NodeRange(start_line=0, start_column=0, end_line=5, end_column=10)
        assert nr.start_line == 0
        assert nr.end_line == 5
