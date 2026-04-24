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

from openlia.formula.engine import MAX_AST_DEPTH, MAX_NODE_COUNT, FormulaError
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
        self.node_count = 0
        self.depth = 0

    def _enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_AST_DEPTH:
            t = self.peek
            raise FormulaError(
                f"expression exceeds max depth of {MAX_AST_DEPTH}",
                line=t.line,
                col=t.col,
            )

    def _exit(self) -> None:
        self.depth -= 1

    def _count(self) -> None:
        self.node_count += 1
        if self.node_count > MAX_NODE_COUNT:
            t = self.peek
            raise FormulaError(
                f"expression exceeds max node count of {MAX_NODE_COUNT}",
                line=t.line,
                col=t.col,
            )

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
        self._enter()
        try:
            left = self.or_expr()
            if self.accept(TokenKind.IF):
                cond = self.or_expr()
                self.expect(TokenKind.ELSE, "'else'")
                other = self.ternary()
                self._count()
                return IfElse(
                    condition=cond,
                    then_branch=left,
                    else_branch=other,
                    line=left.line,
                    col=left.col,
                )
            return left
        finally:
            self._exit()

    def or_expr(self) -> Expression:
        self._enter()
        try:
            node = self.and_expr()
            while self.accept(TokenKind.OR):
                right = self.and_expr()
                self._count()
                node = BinaryOp("or", node, right, line=node.line, col=node.col)
            return node
        finally:
            self._exit()

    def and_expr(self) -> Expression:
        self._enter()
        try:
            node = self.not_expr()
            while self.accept(TokenKind.AND):
                right = self.not_expr()
                self._count()
                node = BinaryOp("and", node, right, line=node.line, col=node.col)
            return node
        finally:
            self._exit()

    def not_expr(self) -> Expression:
        self._enter()
        try:
            if self.accept(TokenKind.NOT):
                operand = self.not_expr()
                self._count()
                return UnaryOp("not", operand, line=operand.line, col=operand.col)
            return self.comparison()
        finally:
            self._exit()

    def comparison(self) -> Expression:
        self._enter()
        try:
            node = self.additive()
            while self.peek.kind in _COMPARISON_KINDS:
                op_tok = self.advance()
                right = self.additive()
                self._count()
                node = BinaryOp(
                    _COMPARISON_KINDS[op_tok.kind],
                    node,
                    right,
                    line=node.line,
                    col=node.col,
                )
            return node
        finally:
            self._exit()

    def additive(self) -> Expression:
        self._enter()
        try:
            node = self.multiplicative()
            while True:
                if self.accept(TokenKind.PLUS):
                    right = self.multiplicative()
                    self._count()
                    node = BinaryOp("+", node, right, line=node.line, col=node.col)
                elif self.accept(TokenKind.MINUS):
                    right = self.multiplicative()
                    self._count()
                    node = BinaryOp("-", node, right, line=node.line, col=node.col)
                else:
                    return node
        finally:
            self._exit()

    def multiplicative(self) -> Expression:
        self._enter()
        try:
            node = self.unary()
            while True:
                if self.accept(TokenKind.STAR):
                    right = self.unary()
                    self._count()
                    node = BinaryOp("*", node, right, line=node.line, col=node.col)
                elif self.accept(TokenKind.SLASH):
                    right = self.unary()
                    self._count()
                    node = BinaryOp("/", node, right, line=node.line, col=node.col)
                elif self.accept(TokenKind.PERCENT):
                    right = self.unary()
                    self._count()
                    node = BinaryOp("%", node, right, line=node.line, col=node.col)
                else:
                    return node
        finally:
            self._exit()

    def unary(self) -> Expression:
        self._enter()
        try:
            if self.accept(TokenKind.MINUS):
                operand = self.unary()
                self._count()
                return UnaryOp("-", operand, line=operand.line, col=operand.col)
            return self.power()
        finally:
            self._exit()

    def power(self) -> Expression:
        self._enter()
        try:
            base = self.primary()
            if self.accept(TokenKind.DOUBLESTAR):
                exponent = self.unary()  # right-associative
                self._count()
                return BinaryOp("**", base, exponent, line=base.line, col=base.col)
            return base
        finally:
            self._exit()

    def primary(self) -> Expression:
        self._enter()
        try:
            t = self.peek
            if t.kind is TokenKind.NUMBER:
                self.advance()
                self._count()
                return Literal(value=t.value, line=t.line, col=t.col)
            if t.kind is TokenKind.TRUE:
                self.advance()
                self._count()
                return Literal(value=True, line=t.line, col=t.col)
            if t.kind is TokenKind.FALSE:
                self.advance()
                self._count()
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
                    self._count()
                    return Call(callee=t.value, args=args, line=t.line, col=t.col)
                if self.accept(TokenKind.LBRACKET):
                    self._count()
                    return self._parse_history_index(t)
                self._count()
                return Var(name=t.value, line=t.line, col=t.col)

            raise FormulaError(
                f"expected expression but found {t.kind.name}",
                line=t.line,
                col=t.col,
            )
        finally:
            self._exit()

    def _parse_history_index(self, ident: Token) -> Expression:
        # Already consumed the opening '['. Expect ``t - NUMBER`` then ']'.
        t_tok = self.peek
        if t_tok.kind is not TokenKind.IDENT or t_tok.value != "t":
            raise FormulaError(
                "history index must start with 't'",
                line=t_tok.line,
                col=t_tok.col,
            )
        self.advance()
        minus = self.peek
        if minus.kind is not TokenKind.MINUS:
            raise FormulaError(
                "history index must use '-' (e.g. 'price[t-3]')",
                line=minus.line,
                col=minus.col,
            )
        self.advance()
        number = self.peek
        if number.kind is not TokenKind.NUMBER:
            raise FormulaError(
                "history index requires an integer lag",
                line=number.line,
                col=number.col,
            )
        self.advance()
        lag_val = number.value
        if float(lag_val).is_integer() is False or lag_val < 0:
            raise FormulaError(
                "history lag must be a non-negative integer",
                line=number.line,
                col=number.col,
            )
        self.expect(TokenKind.RBRACKET, "']'")
        return HistoricalVar(
            name=ident.value,
            lag=int(lag_val),
            line=ident.line,
            col=ident.col,
        )


def parse(source: str) -> Expression:
    try:
        tokens = tokenize(source)
    except LexError as exc:
        raise FormulaError(str(exc), line=exc.line, col=exc.col) from exc
    return _Parser(tokens).parse()
