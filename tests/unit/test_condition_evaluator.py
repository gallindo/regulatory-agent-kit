"""Tests for the condition evaluator module."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.plugins.condition_evaluator import (
    ConditionEvaluator,
    FileContext,
    detect_language,
)

# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    @pytest.mark.parametrize(
        ("suffix", "expected"),
        [
            (".py", "python"),
            (".js", "javascript"),
            (".ts", "typescript"),
            (".jsx", "javascript"),
            (".tsx", "typescript"),
            (".java", "java"),
            (".kt", "kotlin"),
            (".go", "go"),
            (".rs", "rust"),
            (".rb", "ruby"),
            (".txt", ""),
            (".css", ""),
        ],
    )
    def test_extensions(self, suffix: str, expected: str) -> None:
        assert detect_language(Path(f"file{suffix}")) == expected


# ---------------------------------------------------------------------------
# FileContext
# ---------------------------------------------------------------------------

SAMPLE_PYTHON = """\
import os
from pathlib import Path

@dataclass
class MyService:
    pass

@deprecated
class OldService:
    pass

def handle_request():
    pass

def process():
    pass
"""

SAMPLE_JS = """\
import { foo } from 'bar';
const baz = require('qux');

class Widget {}

function render() {}
const helper = () => {};
"""

SAMPLE_JAVA = """\
import com.example.Service;
import java.util.List;

public class MyController {
    public void handleRequest() {}
    private String getName() { return ""; }
}
"""


class TestFileContext:
    def test_from_file_python(self, tmp_path: Path) -> None:
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")
        ctx = FileContext.from_file(f)

        assert ctx.language == "python"
        assert "os" in ctx.has_imports
        assert "pathlib" in ctx.has_imports
        assert "handle_request" in ctx.has_functions
        assert "process" in ctx.has_functions
        assert "MyService" in ctx.has_classes
        assert "OldService" in ctx.has_classes
        assert "dataclass" in ctx.has_decorators
        assert "deprecated" in ctx.has_decorators
        assert ctx.file_content == SAMPLE_PYTHON

    def test_from_file_javascript(self, tmp_path: Path) -> None:
        f = tmp_path / "widget.js"
        f.write_text(SAMPLE_JS, encoding="utf-8")
        ctx = FileContext.from_file(f)

        assert ctx.language == "javascript"
        assert "bar" in ctx.has_imports
        assert "qux" in ctx.has_imports
        assert "Widget" in ctx.has_classes
        assert "render" in ctx.has_functions

    def test_from_file_java(self, tmp_path: Path) -> None:
        f = tmp_path / "Controller.java"
        f.write_text(SAMPLE_JAVA, encoding="utf-8")
        ctx = FileContext.from_file(f)

        assert ctx.language == "java"
        assert "com.example.Service" in ctx.has_imports
        assert "java.util.List" in ctx.has_imports
        assert "MyController" in ctx.has_classes
        assert "handleRequest" in ctx.has_functions
        assert "getName" in ctx.has_functions

    def test_from_file_nonexistent(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.py"
        ctx = FileContext.from_file(f)
        assert ctx.language == "python"
        assert ctx.file_content == ""
        assert ctx.has_imports == []

    def test_from_file_unknown_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")
        ctx = FileContext.from_file(f)
        assert ctx.language == ""
        # No symbol extraction for unknown languages
        assert ctx.has_imports == []
        assert ctx.has_functions == []

    def test_from_file_large_file_skipped(self, tmp_path: Path) -> None:
        """Files larger than 1MB are not read."""
        f = tmp_path / "big.py"
        f.write_text("x" * 1_000_001, encoding="utf-8")
        ctx = FileContext.from_file(f)
        assert ctx.file_content == ""


# ---------------------------------------------------------------------------
# ConditionEvaluator
# ---------------------------------------------------------------------------


def _python_context(
    *,
    imports: list[str] | None = None,
    functions: list[str] | None = None,
    classes: list[str] | None = None,
    decorators: list[str] | None = None,
    content: str = "",
) -> FileContext:
    """Build a minimal FileContext for testing."""
    return FileContext(
        path="test.py",
        language="python",
        has_imports=imports or [],
        has_functions=functions or [],
        has_classes=classes or [],
        has_decorators=decorators or [],
        file_content=content,
    )


class TestConditionEvaluator:
    def setup_method(self) -> None:
        self.evaluator = ConditionEvaluator()

    # -- empty / whitespace --

    def test_empty_condition_returns_true(self) -> None:
        result = self.evaluator.evaluate("", _python_context())
        assert result.is_static is True
        assert result.evaluated is True
        assert result.result is True

    def test_whitespace_condition_returns_true(self) -> None:
        result = self.evaluator.evaluate("   ", _python_context())
        assert result.result is True

    # -- parse error --

    def test_parse_error(self) -> None:
        result = self.evaluator.evaluate("totally invalid ^^^ expression", _python_context())
        assert result.evaluated is False
        assert result.result is None
        assert "Parse error" in result.error

    # -- has_decorator --

    def test_has_decorator_match(self) -> None:
        ctx = _python_context(decorators=["dataclass", "deprecated"])
        result = self.evaluator.evaluate("has_decorator(@dataclass)", ctx)
        assert result.is_static is True
        assert result.evaluated is True
        assert result.result is True

    def test_has_decorator_no_match(self) -> None:
        ctx = _python_context(decorators=["dataclass"])
        result = self.evaluator.evaluate("has_decorator(@deprecated)", ctx)
        assert result.result is False

    # -- has_annotation --

    def test_has_annotation_match(self) -> None:
        ctx = _python_context(decorators=["AuditLog"])
        result = self.evaluator.evaluate("has_annotation(@AuditLog)", ctx)
        assert result.result is True

    # -- has_method --

    def test_has_method_match(self) -> None:
        ctx = _python_context(functions=["handleRequest", "process"])
        result = self.evaluator.evaluate("has_method(handleRequest)", ctx)
        assert result.result is True

    def test_has_method_no_match(self) -> None:
        ctx = _python_context(functions=["process"])
        result = self.evaluator.evaluate("has_method(handleRequest)", ctx)
        assert result.result is False

    # -- class implements / inherits --

    def test_class_implements_match(self) -> None:
        ctx = _python_context(classes=["ICTServiceImpl"])
        result = self.evaluator.evaluate("class implements ICTService", ctx)
        assert result.result is True

    def test_class_implements_no_match(self) -> None:
        ctx = _python_context(classes=["Widget"])
        result = self.evaluator.evaluate("class implements ICTService", ctx)
        assert result.result is False

    def test_class_inherits_match(self) -> None:
        ctx = _python_context(classes=["BaseController"])
        result = self.evaluator.evaluate("class inherits BaseController", ctx)
        assert result.result is True

    # -- class_name matches --

    def test_class_name_matches(self) -> None:
        ctx = _python_context(classes=["ServiceImpl", "WidgetFactory"])
        result = self.evaluator.evaluate('class_name matches "Service.*Impl"', ctx)
        assert result.result is True

    def test_class_name_matches_no_hit(self) -> None:
        ctx = _python_context(classes=["Widget"])
        result = self.evaluator.evaluate('class_name matches "Service.*"', ctx)
        assert result.result is False

    # -- has_key --

    def test_has_key_match(self) -> None:
        ctx = _python_context(content="resilience.rto = 30\nresilience.rpo = 15\n")
        result = self.evaluator.evaluate("has_key(resilience.rto)", ctx)
        assert result.result is True

    def test_has_key_no_match(self) -> None:
        ctx = _python_context(content="something_else = 1\n")
        result = self.evaluator.evaluate("has_key(resilience.rto)", ctx)
        assert result.result is False

    # -- compound expressions --

    def test_and_both_true(self) -> None:
        ctx = _python_context(
            classes=["ServiceImpl"],
            decorators=["AuditLog"],
        )
        result = self.evaluator.evaluate(
            "class implements Service AND has_annotation(@AuditLog)", ctx
        )
        assert result.result is True

    def test_and_one_false(self) -> None:
        ctx = _python_context(classes=["ServiceImpl"], decorators=[])
        result = self.evaluator.evaluate(
            "class implements Service AND has_annotation(@AuditLog)", ctx
        )
        assert result.result is False

    def test_or_one_true(self) -> None:
        ctx = _python_context(functions=["foo"])
        result = self.evaluator.evaluate("has_method(foo) OR has_method(bar)", ctx)
        assert result.result is True

    def test_not_true(self) -> None:
        ctx = _python_context(decorators=[])
        result = self.evaluator.evaluate("NOT has_annotation(@AuditLog)", ctx)
        assert result.result is True

    def test_not_false(self) -> None:
        ctx = _python_context(decorators=["AuditLog"])
        result = self.evaluator.evaluate("NOT has_annotation(@AuditLog)", ctx)
        assert result.result is False

    # -- evaluate_rule_conditions --

    def test_evaluate_rule_conditions_multiple(self) -> None:
        ctx = _python_context(
            functions=["handleRequest"],
            classes=["ServiceImpl"],
        )
        results = self.evaluator.evaluate_rule_conditions(
            ["has_method(handleRequest)", "class implements Service"],
            ctx,
        )
        assert len(results) == 2
        assert all(r.evaluated for r in results)
        assert all(r.result is True for r in results)

    def test_evaluate_rule_conditions_empty(self) -> None:
        results = self.evaluator.evaluate_rule_conditions([], _python_context())
        assert results == []


# ---------------------------------------------------------------------------
# Integration: FileContext.from_file + ConditionEvaluator
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Evaluate conditions against real files on disk."""

    def test_python_file_has_decorator(self, tmp_path: Path) -> None:
        f = tmp_path / "svc.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")
        ctx = FileContext.from_file(f)
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("has_decorator(@dataclass)", ctx)
        assert result.result is True

    def test_python_file_class_implements(self, tmp_path: Path) -> None:
        f = tmp_path / "svc.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")
        ctx = FileContext.from_file(f)
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("class implements MyService", ctx)
        assert result.result is True

    def test_python_file_not_matching(self, tmp_path: Path) -> None:
        f = tmp_path / "svc.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")
        ctx = FileContext.from_file(f)
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate("has_method(nonexistent)", ctx)
        assert result.result is False
