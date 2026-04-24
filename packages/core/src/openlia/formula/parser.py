"""Pratt-style parser producing a typed AST.

The grammar (in pseudo-EBNF, loosest precedence first):

    expr        := ternary
    ternary     := or_expr ("if" or_expr "else" expr)?
    or_expr     := and_expr ("or" and_expr)*
    and_expr    := not_expr ("and" not_expr)*
    not_expr    := "not" not_expr | comparison
    comparison  := additive ( ("<"|"<="|">"|">="|"=="|"!=") additive )*
    additive    := multiplicative ( ("+"|"-") multiplicative )*
    multiplicative := unary ( ("*"|"/"|"%") unary )*
    unary       := "-" unary | power
    power       := primary ( "**" unary )?
    primary     := NUMBER | TRUE | FALSE | IDENT ( "[" history "]" )? | call | "(" expr ")"
    call        := IDENT "(" [ expr ("," expr)* ] ")"
    history     := "t" "-" NUMBER            # populated in Task 6
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openlia.formula.engine import FormulaError
from openlia.formula.lexer import LexError, tokenize
from openlia.formula.tokens import Token, TokenKind


class Expression:
    """Base class for every AST node."""

    # Source span (set by parser where available). Evaluator reads these for
    # richer error messages.
    line: int = 0
    col: int = 0


@dataclass
class Literal(Expression):
    value: float | bool
    line: int = 0
    col: int = 0


@dataclass
class Var(Expression):
    name: str
    line: int = 0
    col: int = 0


@dataclass
class HistoricalVar(Expression):
    """Placeholder; body lands in Task 6."""

    name: str
    lag: int
    line: int = 0
    col: int = 0


@dataclass
class BinaryOp(Expression):
    op: str
    left: Expression
    right: Expression
    line: int = 0
    col: int = 0


@dataclass
class UnaryOp(Expression):
    op: str
    operand: Expression
    line: int = 0
    col: int = 0


@dataclass
class Call(Expression):
    callee: str
    args: list[Expression] = field(default_factory=list)
    line: int = 0
    col: int = 0


@dataclass
class IfElse(Expression):
    condition: Expression
    then_branch: Expression
    else_branch: Expression
    line: int = 0
    col: int = 0


_COMPARISON_KINDS: dict[TokenKind, str] = {
    TokenKind.LT: "<",
    TokenKind.LE: "<=",
    TokenKind.GT: ">",
    TokenKind.GE: ">=",
    TokenKind.EQ: "==",
    TokenKind.NE: "!=",
}


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ---- navigation ----
    @property
    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def accept(self, kind: TokenKind) -> Token | None:
        if self.peek.kind is kind:
            return self.advance()
        return None

    def expect(self, kind: TokenKind, what: str) -> Token:
        if self.peek.kind is not kind:
            t = self.peek
            raise FormulaError(
                f"expected {what} but found {t.kind.name}",
                line=t.line,
                col=t.col,
            )
        return self.advance()

    # ---- grammar ----
    def parse(self) -> Expression:
        node = self.ternary()
        if self.peek.kind is not TokenKind.EOF:
            t = self.peek
            raise FormulaError(
                f"unexpected token {t.kind.name} after expression",
                line=t.line,
                col=t.col,
            )
        return node

    def ternary(self) -> Expression:
        left = self.or_expr()
        if self.accept(TokenKind.IF):
            cond = self.or_expr()
            self.expect(TokenKind.ELSE, "'else'")
            other = self.ternary()
            return IfElse(
                condition=cond,
                then_branch=left,
                else_branch=other,
                line=left.line,
                col=left.col,
            )
        return left

    def or_expr(self) -> Expression:
        node = self.and_expr()
        while self.accept(TokenKind.OR):
            right = self.and_expr()
            node = BinaryOp("or", node, right, line=node.line, col=node.col)
        return node

    def and_expr(self) -> Expression:
        node = self.not_expr()
        while self.accept(TokenKind.AND):
            right = self.not_expr()
            node = BinaryOp("and", node, right, line=node.line, col=node.col)
        return node

    def not_expr(self) -> Expression:
        if self.accept(TokenKind.NOT):
            operand = self.not_expr()
            return UnaryOp("not", operand, line=operand.line, col=operand.col)
        return self.comparison()

    def comparison(self) -> Expression:
        node = self.additive()
        while self.peek.kind in _COMPARISON_KINDS:
            op_tok = self.advance()
            right = self.additive()
            node = BinaryOp(
                _COMPARISON_KINDS[op_tok.kind],
                node,
                right,
                line=node.line,
                col=node.col,
            )
        return node

    def additive(self) -> Expression:
        node = self.multiplicative()
        while True:
            if self.accept(TokenKind.PLUS):
                right = self.multiplicative()
                node = BinaryOp("+", node, right, line=node.line, col=node.col)
            elif self.accept(TokenKind.MINUS):
                right = self.multiplicative()
                node = BinaryOp("-", node, right, line=node.line, col=node.col)
            else:
                return node

    def multiplicative(self) -> Expression:
        node = self.unary()
        while True:
            if self.accept(TokenKind.STAR):
                right = self.unary()
                node = BinaryOp("*", node, right, line=node.line, col=node.col)
            elif self.accept(TokenKind.SLASH):
                right = self.unary()
                node = BinaryOp("/", node, right, line=node.line, col=node.col)
            elif self.accept(TokenKind.PERCENT):
                right = self.unary()
                node = BinaryOp("%", node, right, line=node.line, col=node.col)
            else:
                return node

    def unary(self) -> Expression:
        if self.accept(TokenKind.MINUS):
            operand = self.unary()
            return UnaryOp("-", operand, line=operand.line, col=operand.col)
        return self.power()

    def power(self) -> Expression:
        base = self.primary()
        if self.accept(TokenKind.DOUBLESTAR):
            exponent = self.unary()  # right-associative
            return BinaryOp("**", base, exponent, line=base.line, col=base.col)
        return base

    def primary(self) -> Expression:
        t = self.peek
        if t.kind is TokenKind.NUMBER:
            self.advance()
            return Literal(value=t.value, line=t.line, col=t.col)
        if t.kind is TokenKind.TRUE:
            self.advance()
            return Literal(value=True, line=t.line, col=t.col)
        if t.kind is TokenKind.FALSE:
            self.advance()
            return Literal(value=False, line=t.line, col=t.col)
        if t.kind is TokenKind.LPAREN:
            self.advance()
            node = self.ternary()
            self.expect(TokenKind.RPAREN, "')'")
            return node
        if t.kind is TokenKind.IDENT:
            self.advance()
            # Function call?
            if self.accept(TokenKind.LPAREN):
                args: list[Expression] = []
                if self.peek.kind is not TokenKind.RPAREN:
                    args.append(self.ternary())
                    while self.accept(TokenKind.COMMA):
                        args.append(self.ternary())
                self.expect(TokenKind.RPAREN, "')'")
                return Call(callee=t.value, args=args, line=t.line, col=t.col)
            # Historical indexing lands in Task 6.
            if self.accept(TokenKind.LBRACKET):
                return self._parse_history_index(t)
            return Var(name=t.value, line=t.line, col=t.col)

        raise FormulaError(
            f"expected expression but found {t.kind.name}",
            line=t.line,
            col=t.col,
        )

    # Placeholder; Task 6 replaces the body with full `[t-N]` parsing.
    def _parse_history_index(self, ident: Token) -> Expression:  # pragma: no cover
        raise FormulaError(
            "historical indexing '[t-N]' lands in Task 6",
            line=ident.line,
            col=ident.col,
        )


def parse(source: str) -> Expression:
    try:
        tokens = tokenize(source)
    except LexError as exc:
        raise FormulaError(str(exc), line=exc.line, col=exc.col) from exc
    return _Parser(tokens).parse()
