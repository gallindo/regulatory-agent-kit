"""Condition DSL parser — recursive descent parser for regulation rule conditions.

Grammar (EBNF):
    expression  = or_expr
    or_expr     = and_expr ( "OR" and_expr )*
    and_expr    = not_expr ( "AND" not_expr )*
    not_expr    = "NOT" not_expr | primary
    primary     = predicate | "(" expression ")"
    predicate   = class_pred | annotation_pred | method_pred | key_pred | match_pred
    class_pred  = "class" ("implements" | "inherits") IDENTIFIER
    annotation_pred = ("has_annotation" | "has_decorator") "(" "@" IDENTIFIER ")"
    method_pred = "has_method" "(" IDENTIFIER ")"
    key_pred    = "has_key" "(" DOTTED_PATH ")"
    match_pred  = "class_name" "matches" QUOTED_STRING

Operator precedence (high → low): NOT > AND > OR
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from regulatory_agent_kit.exceptions import ConditionParseError

# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

NodeType = Literal["AND", "OR", "NOT", "PREDICATE"]

PredicateOperator = Literal[
    "implements",
    "inherits",
    "has_annotation",
    "has_decorator",
    "has_method",
    "has_key",
    "matches",
]

STATIC_PREDICATES: frozenset[str] = frozenset(
    {
        "implements",
        "inherits",
        "has_annotation",
        "has_decorator",
        "has_method",
        "has_key",
        "matches",
    }
)


@dataclass(frozen=True)
class Predicate:
    """A leaf predicate in the condition AST."""

    operator: PredicateOperator
    argument: str


@dataclass
class ConditionAST:
    """A node in the condition AST."""

    node_type: NodeType
    children: list[ConditionAST] = field(default_factory=list)
    predicate: Predicate | None = None


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<KEYWORD>AND|OR|NOT)(?=\s|\(|$)
      | (?P<PAREN>[()@])
      | (?P<QUOTED>"[^"]*")
      | (?P<WORD>[A-Za-z_][A-Za-z0-9_.*/]*)
    )\s*
    """,
    re.VERBOSE,
)


def _tokenize(expression: str) -> list[str]:
    """Tokenize a condition DSL expression into a list of token strings."""
    tokens: list[str] = []
    pos = 0
    while pos < len(expression):
        if expression[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(expression, pos)
        if m is None:
            msg = f"Unexpected character at position {pos}: '{expression[pos]}'"
            raise ConditionParseError(msg)
        token = m.group("KEYWORD") or m.group("PAREN") or m.group("QUOTED") or m.group("WORD")
        if token is None:  # pragma: no cover
            msg = f"Unexpected token at position {pos}"
            raise ConditionParseError(msg)
        tokens.append(token)
        pos = m.end()
    return tokens


# ---------------------------------------------------------------------------
# Recursive descent parser
# ---------------------------------------------------------------------------


class _Parser:
    """Stateful recursive descent parser for the Condition DSL."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _current(self) -> str | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self, expected: str | None = None) -> str:
        tok = self._current()
        if tok is None:
            msg = f"Unexpected end of expression; expected '{expected}'"
            raise ConditionParseError(msg)
        if expected is not None and tok != expected:
            msg = f"Expected '{expected}' but got '{tok}' at token {self._pos}"
            raise ConditionParseError(msg)
        self._pos += 1
        return tok

    # --- Grammar rules ---

    def parse_expression(self) -> ConditionAST:
        ast = self._parse_or()
        if self._current() is not None:
            msg = f"Unexpected token '{self._current()}' at position {self._pos}"
            raise ConditionParseError(msg)
        return ast

    def _parse_or(self) -> ConditionAST:
        left = self._parse_and()
        while self._current() == "OR":
            self._consume("OR")
            right = self._parse_and()
            left = ConditionAST(node_type="OR", children=[left, right])
        return left

    def _parse_and(self) -> ConditionAST:
        left = self._parse_not()
        while self._current() == "AND":
            self._consume("AND")
            right = self._parse_not()
            left = ConditionAST(node_type="AND", children=[left, right])
        return left

    def _parse_not(self) -> ConditionAST:
        if self._current() == "NOT":
            self._consume("NOT")
            child = self._parse_not()
            return ConditionAST(node_type="NOT", children=[child])
        return self._parse_primary()

    def _parse_primary(self) -> ConditionAST:
        if self._current() == "(":
            self._consume("(")
            expr = self._parse_or()
            self._consume(")")
            return expr
        return self._parse_predicate()

    def _parse_predicate(self) -> ConditionAST:
        tok = self._current()
        if tok is None:
            msg = "Unexpected end of expression; expected a predicate"
            raise ConditionParseError(msg)

        # class implements/inherits IDENTIFIER
        if tok == "class":
            self._consume("class")
            op_tok = self._current()
            if op_tok not in ("implements", "inherits"):
                msg = f"Expected 'implements' or 'inherits' after 'class', got '{op_tok}'"
                raise ConditionParseError(msg)
            self._consume()
            arg = self._consume()
            return ConditionAST(
                node_type="PREDICATE",
                predicate=Predicate(operator=op_tok, argument=arg),  # type: ignore[arg-type]
            )

        # has_annotation(@X) / has_decorator(@X)
        if tok in ("has_annotation", "has_decorator"):
            op = self._consume()
            self._consume("(")
            self._consume("@")
            arg = self._consume()
            self._consume(")")
            return ConditionAST(
                node_type="PREDICATE",
                predicate=Predicate(operator=op, argument=arg),  # type: ignore[arg-type]
            )

        # has_method(X)
        if tok == "has_method":
            self._consume("has_method")
            self._consume("(")
            arg = self._consume()
            self._consume(")")
            return ConditionAST(
                node_type="PREDICATE",
                predicate=Predicate(operator="has_method", argument=arg),
            )

        # has_key(X.Y.Z)
        if tok == "has_key":
            self._consume("has_key")
            self._consume("(")
            arg = self._consume()
            self._consume(")")
            return ConditionAST(
                node_type="PREDICATE",
                predicate=Predicate(operator="has_key", argument=arg),
            )

        # class_name matches "regex"
        if tok == "class_name":
            self._consume("class_name")
            self._consume("matches")
            raw = self._consume()
            # Strip quotes from quoted string
            arg = raw.strip('"')
            return ConditionAST(
                node_type="PREDICATE",
                predicate=Predicate(operator="matches", argument=arg),
            )

        msg = f"Unknown predicate: '{tok}' at token {self._pos}"
        raise ConditionParseError(msg)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(expression: str) -> ConditionAST:
    """Parse a Condition DSL expression into an AST.

    Raises ConditionParseError on syntax errors.
    """
    expression = expression.strip()
    if not expression:
        msg = "Empty condition expression"
        raise ConditionParseError(msg)
    tokens = _tokenize(expression)
    parser = _Parser(tokens)
    return parser.parse_expression()


def can_evaluate_statically(ast: ConditionAST) -> bool:
    """Return True if the entire AST can be evaluated without an LLM."""
    if ast.node_type == "PREDICATE":
        if ast.predicate is None:
            return False
        return ast.predicate.operator in STATIC_PREDICATES
    return all(can_evaluate_statically(child) for child in ast.children)


def to_llm_prompt(ast: ConditionAST) -> str:
    """Convert a condition AST into a natural-language prompt for LLM evaluation."""
    return _ast_to_text(ast)


def _ast_to_text(ast: ConditionAST) -> str:
    if ast.node_type == "PREDICATE" and ast.predicate is not None:
        op = ast.predicate.operator
        arg = ast.predicate.argument
        descriptions: dict[str, str] = {
            "implements": f"the class implements the '{arg}' interface",
            "inherits": f"the class inherits from '{arg}'",
            "has_annotation": f"the code has the @{arg} annotation",
            "has_decorator": f"the code has the @{arg} decorator",
            "has_method": f"the code defines a method named '{arg}'",
            "has_key": f"the configuration contains the key '{arg}'",
            "matches": f"the class name matches the pattern '{arg}'",
        }
        return descriptions.get(op, f"{op}({arg})")

    if ast.node_type == "NOT" and ast.children:
        return f"it is NOT the case that {_ast_to_text(ast.children[0])}"
    if ast.node_type == "AND" and len(ast.children) == 2:
        left = _ast_to_text(ast.children[0])
        right = _ast_to_text(ast.children[1])
        return f"({left} AND {right})"
    if ast.node_type == "OR" and len(ast.children) == 2:
        left = _ast_to_text(ast.children[0])
        right = _ast_to_text(ast.children[1])
        return f"({left} OR {right})"

    return "unknown condition"
