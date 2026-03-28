"""Tests for the Condition DSL parser (Phase 3)."""

from __future__ import annotations

import pytest

from regulatory_agent_kit.exceptions import ConditionParseError
from regulatory_agent_kit.plugins.condition_dsl import (
    can_evaluate_statically,
    parse,
    to_llm_prompt,
)


class TestParse:
    def test_implements(self) -> None:
        ast = parse("class implements Service")
        assert ast.node_type == "PREDICATE"
        assert ast.predicate is not None
        assert ast.predicate.operator == "implements"
        assert ast.predicate.argument == "Service"

    def test_inherits(self) -> None:
        ast = parse("class inherits BaseController")
        assert ast.predicate is not None
        assert ast.predicate.operator == "inherits"

    def test_has_annotation(self) -> None:
        ast = parse("has_annotation(@AuditLog)")
        assert ast.predicate is not None
        assert ast.predicate.operator == "has_annotation"
        assert ast.predicate.argument == "AuditLog"

    def test_has_decorator(self) -> None:
        ast = parse("has_decorator(@deprecated)")
        assert ast.predicate is not None
        assert ast.predicate.operator == "has_decorator"
        assert ast.predicate.argument == "deprecated"

    def test_has_method(self) -> None:
        ast = parse("has_method(handleRequest)")
        assert ast.predicate is not None
        assert ast.predicate.operator == "has_method"
        assert ast.predicate.argument == "handleRequest"

    def test_has_key(self) -> None:
        ast = parse("has_key(resilience.rto)")
        assert ast.predicate is not None
        assert ast.predicate.operator == "has_key"
        assert ast.predicate.argument == "resilience.rto"

    def test_matches(self) -> None:
        ast = parse('class_name matches "Service.*Impl"')
        assert ast.predicate is not None
        assert ast.predicate.operator == "matches"
        assert ast.predicate.argument == "Service.*Impl"

    def test_and(self) -> None:
        ast = parse("class implements Service AND has_annotation(@AuditLog)")
        assert ast.node_type == "AND"
        assert len(ast.children) == 2

    def test_or(self) -> None:
        ast = parse("has_method(foo) OR has_method(bar)")
        assert ast.node_type == "OR"
        assert len(ast.children) == 2

    def test_not(self) -> None:
        ast = parse("NOT has_annotation(@AuditLog)")
        assert ast.node_type == "NOT"
        assert len(ast.children) == 1

    def test_precedence_not_binds_tighter_than_and(self) -> None:
        # "A AND NOT B" should be "A AND (NOT B)"
        ast = parse("class implements Service AND NOT has_annotation(@AuditLog)")
        assert ast.node_type == "AND"
        assert ast.children[1].node_type == "NOT"

    def test_precedence_and_binds_tighter_than_or(self) -> None:
        # "A OR B AND NOT C" should be "A OR (B AND (NOT C))"
        ast = parse("has_method(a) OR class implements B AND NOT has_annotation(@C)")
        assert ast.node_type == "OR"
        assert ast.children[1].node_type == "AND"

    def test_parentheses_override_precedence(self) -> None:
        ast = parse("(has_method(a) OR has_method(b)) AND has_method(c)")
        assert ast.node_type == "AND"
        assert ast.children[0].node_type == "OR"

    def test_nested_parentheses(self) -> None:
        ast = parse("NOT (has_method(a) AND (has_method(b) OR has_method(c)))")
        assert ast.node_type == "NOT"
        assert ast.children[0].node_type == "AND"

    def test_empty_expression_raises(self) -> None:
        with pytest.raises(ConditionParseError, match=r"[Ee]mpty"):
            parse("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ConditionParseError, match=r"[Ee]mpty"):
            parse("   ")

    def test_unclosed_paren_raises(self) -> None:
        with pytest.raises(ConditionParseError):
            parse("(has_method(foo)")

    def test_unknown_predicate_raises(self) -> None:
        with pytest.raises(ConditionParseError, match=r"[Uu]nknown"):
            parse("unknown_pred(x)")

    def test_unexpected_end_raises(self) -> None:
        with pytest.raises(ConditionParseError):
            parse("class implements")


class TestCanEvaluateStatically:
    @pytest.mark.parametrize(
        "expr",
        [
            "class implements Service",
            "class inherits Base",
            "has_annotation(@AuditLog)",
            "has_decorator(@deprecated)",
            "has_method(handle)",
            "has_key(resilience.rto)",
            'class_name matches "Foo"',
        ],
    )
    def test_static_predicates(self, expr: str) -> None:
        ast = parse(expr)
        assert can_evaluate_statically(ast) is True

    def test_compound_static(self) -> None:
        ast = parse("class implements Service AND NOT has_annotation(@AuditLog)")
        assert can_evaluate_statically(ast) is True


class TestToLLMPrompt:
    def test_simple_predicate(self) -> None:
        ast = parse("class implements Service")
        prompt = to_llm_prompt(ast)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Service" in prompt

    def test_compound_expression(self) -> None:
        ast = parse("class implements Service AND NOT has_annotation(@AuditLog)")
        prompt = to_llm_prompt(ast)
        assert "AND" in prompt
        assert "NOT" in prompt
        assert "AuditLog" in prompt

    def test_or_expression(self) -> None:
        ast = parse("has_method(foo) OR has_method(bar)")
        prompt = to_llm_prompt(ast)
        assert "OR" in prompt
