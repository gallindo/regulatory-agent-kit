"""Evaluate condition DSL expressions against repository files.

Connects the DSL parser to actual file analysis by building a
``FileContext`` from source files and evaluating parsed condition ASTs
against it.  Conditions that can be resolved statically are evaluated
immediately; those requiring semantic understanding produce an LLM
prompt for downstream agent evaluation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 — used at runtime in from_file / detect_language

from regulatory_agent_kit.plugins.condition_dsl import (
    Predicate,
    can_evaluate_statically,
    parse,
    to_llm_prompt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
}


def detect_language(path: Path) -> str:
    """Detect programming language from file extension."""
    return _EXTENSION_TO_LANGUAGE.get(path.suffix, "")


# ---------------------------------------------------------------------------
# Condition result
# ---------------------------------------------------------------------------


@dataclass
class ConditionResult:
    """Result of evaluating a condition against a file."""

    condition: str
    is_static: bool
    evaluated: bool
    result: bool | None  # None if requires LLM
    llm_prompt: str = ""  # Non-empty if needs LLM evaluation
    error: str = ""


# ---------------------------------------------------------------------------
# File context
# ---------------------------------------------------------------------------


@dataclass
class FileContext:
    """Context about a file for condition evaluation."""

    path: str
    language: str = ""
    has_imports: list[str] = field(default_factory=list)
    has_functions: list[str] = field(default_factory=list)
    has_classes: list[str] = field(default_factory=list)
    has_decorators: list[str] = field(default_factory=list)
    file_content: str = ""

    @classmethod
    def from_file(cls, file_path: Path) -> FileContext:
        """Build context from a real file on disk."""
        path_str = str(file_path)
        language = detect_language(file_path)

        context = cls(path=path_str, language=language)

        if file_path.exists() and file_path.stat().st_size < 1_000_000:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                context.file_content = content
                context._extract_symbols(content, language)
            except OSError:
                logger.debug("Could not read file %s", file_path)

        return context

    def _extract_symbols(self, content: str, language: str) -> None:
        """Extract basic symbols (imports, functions, classes, decorators) from file content."""
        if language == "python":
            self._extract_python_symbols(content)
        elif language in ("javascript", "typescript"):
            self._extract_js_symbols(content)
        elif language == "java":
            self._extract_java_symbols(content)

    def _extract_python_symbols(self, content: str) -> None:
        """Extract symbols from Python source."""
        raw_imports = re.findall(r"^(?:from\s+(\S+)\s+)?import\s+(\S+)", content, re.MULTILINE)
        self.has_imports = [m[0] or m[1] for m in raw_imports if any(m)]
        self.has_functions = re.findall(r"^def\s+(\w+)", content, re.MULTILINE)
        self.has_classes = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
        self.has_decorators = re.findall(r"^@(\w+)", content, re.MULTILINE)

    def _extract_js_symbols(self, content: str) -> None:
        """Extract symbols from JavaScript/TypeScript source."""
        # Match both `import ... from 'mod'` and `require('mod')` styles
        es_imports = re.findall(r"from\s+['\"]([^'\"]+)['\"]", content)
        cjs_imports = re.findall(r"require\s*\(\s*['\"]([^'\"]+)['\"]", content)
        self.has_imports = es_imports + cjs_imports
        self.has_functions = re.findall(r"(?:function|const|let|var)\s+(\w+)", content)
        self.has_classes = re.findall(r"class\s+(\w+)", content)

    def _extract_java_symbols(self, content: str) -> None:
        """Extract symbols from Java source."""
        self.has_imports = re.findall(r"^import\s+([\w.]+)", content, re.MULTILINE)
        self.has_classes = re.findall(r"class\s+(\w+)", content)
        self.has_functions = re.findall(
            r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(", content
        )


# ---------------------------------------------------------------------------
# Static evaluation visitor
# ---------------------------------------------------------------------------


class _StaticEvalVisitor:
    """Visitor that evaluates a statically-evaluable AST against a FileContext."""

    def __init__(self, context: FileContext) -> None:
        self._ctx = context

    def visit_predicate(self, predicate: Predicate) -> bool:
        """Evaluate a single predicate against the file context."""
        op = predicate.operator
        arg = predicate.argument

        if op == "implements":
            return self._has_class_like(arg)

        if op == "inherits":
            return self._has_class_like(arg)

        if op in ("has_annotation", "has_decorator"):
            return any(arg.lower() == dec.lower() for dec in self._ctx.has_decorators)

        if op == "has_method":
            return any(arg.lower() == fn.lower() for fn in self._ctx.has_functions)

        if op == "has_key":
            return arg in self._ctx.file_content

        if op == "matches":
            return any(bool(re.search(arg, cls)) for cls in self._ctx.has_classes)

        return False

    def visit_and(self, results: list[bool]) -> bool:
        """All children must be true."""
        return all(results)

    def visit_or(self, results: list[bool]) -> bool:
        """At least one child must be true."""
        return any(results)

    def visit_not(self, results: list[bool]) -> bool:
        """Negate the single child."""
        return not results[0]

    # -- helpers --

    def _has_class_like(self, name: str) -> bool:
        """Check if any class name contains *name* (case-insensitive)."""
        return any(name.lower() in cls.lower() for cls in self._ctx.has_classes)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


@dataclass
class ConditionEvaluator:
    """Evaluates condition DSL expressions against file contexts."""

    def evaluate(self, condition_str: str, context: FileContext) -> ConditionResult:
        """Evaluate a condition expression against a file context.

        Returns a ``ConditionResult`` with the evaluation outcome.  If the
        condition is statically evaluable the ``result`` field is a bool;
        otherwise ``result`` is ``None`` and ``llm_prompt`` contains the
        natural-language prompt for LLM-based evaluation.
        """
        if not condition_str.strip():
            return ConditionResult(
                condition=condition_str,
                is_static=True,
                evaluated=True,
                result=True,
            )

        try:
            ast = parse(condition_str)
        except Exception as exc:
            return ConditionResult(
                condition=condition_str,
                is_static=False,
                evaluated=False,
                result=None,
                error=f"Parse error: {exc}",
            )

        is_static = can_evaluate_statically(ast)

        if is_static:
            visitor = _StaticEvalVisitor(context)
            result = ast.accept(visitor)
            return ConditionResult(
                condition=condition_str,
                is_static=True,
                evaluated=True,
                result=result,
            )

        # Non-static: generate an LLM prompt
        llm_prompt = to_llm_prompt(ast)
        return ConditionResult(
            condition=condition_str,
            is_static=False,
            evaluated=False,
            result=None,
            llm_prompt=llm_prompt,
        )

    def evaluate_rule_conditions(
        self,
        conditions: list[str],
        context: FileContext,
    ) -> list[ConditionResult]:
        """Evaluate multiple conditions for a single rule."""
        return [self.evaluate(c, context) for c in conditions]
