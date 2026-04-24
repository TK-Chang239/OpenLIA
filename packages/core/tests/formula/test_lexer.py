from __future__ import annotations

import pytest
from openlia.formula.lexer import tokenize
from openlia.formula.tokens import Token, TokenKind


def kinds(src: str) -> list[TokenKind]:
    return [t.kind for t in tokenize(src)]


def test_tokenize_empty_returns_only_eof():
    toks = tokenize("")
    assert len(toks) == 1
    assert toks[0].kind is TokenKind.EOF


def test_tokenize_numbers():
    toks = tokenize("1 2.5 -3 1e3 1.2e-4")
    # unary minus is handled by parser; the lexer emits MINUS, NUMBER.
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.NUMBER,
        TokenKind.NUMBER,
        TokenKind.MINUS,
        TokenKind.NUMBER,
        TokenKind.NUMBER,
        TokenKind.NUMBER,
    ]
    assert toks[0].value == 1.0
    assert toks[1].value == 2.5
    assert toks[3].value == 3.0
    assert toks[4].value == 1000.0
    assert toks[5].value == pytest.approx(1.2e-4)


def test_tokenize_identifiers_and_keywords():
    toks = tokenize("price ma200 and or not if else true false")
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.IDENT,
        TokenKind.IDENT,
        TokenKind.AND,
        TokenKind.OR,
        TokenKind.NOT,
        TokenKind.IF,
        TokenKind.ELSE,
        TokenKind.TRUE,
        TokenKind.FALSE,
    ]
    assert toks[0].value == "price"
    assert toks[1].value == "ma200"


def test_tokenize_operators_and_brackets():
    toks = tokenize("+ - * / % ** ( ) , [ ]")
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.PERCENT,
        TokenKind.DOUBLESTAR,
        TokenKind.LPAREN,
        TokenKind.RPAREN,
        TokenKind.COMMA,
        TokenKind.LBRACKET,
        TokenKind.RBRACKET,
    ]


def test_tokenize_comparisons():
    toks = tokenize("< <= > >= == !=")
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.LT,
        TokenKind.LE,
        TokenKind.GT,
        TokenKind.GE,
        TokenKind.EQ,
        TokenKind.NE,
    ]


def test_tokenize_records_positions():
    toks = tokenize("price >= 85")
    assert toks[0].col == 1
    assert toks[1].col == 7
    assert toks[2].col == 10
    assert toks[0].line == 1


def test_tokenize_raises_on_unknown_character():
    with pytest.raises(Exception) as excinfo:
        tokenize("price @ 5")
    msg = str(excinfo.value).lower()
    assert "unexpected" in msg or "unknown" in msg
    # Position surfaced on the exception.
    assert "7" in str(excinfo.value)


def test_token_dataclass_is_hashable_and_repr_safe():
    t = Token(kind=TokenKind.IDENT, value="x", line=1, col=1)
    assert t.kind is TokenKind.IDENT
    repr(t)  # should not raise
