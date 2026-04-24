"""Convert a formula source string into a list of ``Token`` instances.

The lexer recognises numbers, identifiers, keywords, single/double-character
operators, comparison operators, brackets, commas, and the ``[t-N]`` syntax.
Whitespace is skipped. Unknown characters raise ``LexError`` with line/col.
"""

from __future__ import annotations

from openlia.formula.tokens import Token, TokenKind


class LexError(Exception):
    def __init__(self, message: str, *, line: int, col: int) -> None:
        super().__init__(f"{message} at line {line}, col {col}")
        self.line = line
        self.col = col


_KEYWORDS: dict[str, TokenKind] = {
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    line_start = 0
    n = len(source)

    while i < n:
        ch = source[i]
        col = i - line_start + 1

        if ch in " \t":
            i += 1
            continue
        if ch == "\n":
            line += 1
            i += 1
            line_start = i
            continue

        # Numbers (int, float, scientific).
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            j = i
            has_dot = False
            has_exp = False
            while j < n:
                c = source[j]
                if c.isdigit():
                    j += 1
                elif c == "." and not has_dot and not has_exp:
                    has_dot = True
                    j += 1
                elif c in "eE" and not has_exp:
                    has_exp = True
                    j += 1
                    if j < n and source[j] in "+-":
                        j += 1
                else:
                    break
            text = source[i:j]
            try:
                value = float(text)
            except ValueError as exc:
                raise LexError(f"invalid number '{text}'", line=line, col=col) from exc
            tokens.append(Token(TokenKind.NUMBER, value, line=line, col=col, length=j - i))
            i = j
            continue

        # Identifiers / keywords.
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            text = source[i:j]
            kind = _KEYWORDS.get(text, TokenKind.IDENT)
            value: object = text
            if kind is TokenKind.TRUE:
                value = True
            elif kind is TokenKind.FALSE:
                value = False
            tokens.append(Token(kind, value, line=line, col=col, length=j - i))
            i = j
            continue

        # Two-character operators first.
        two = source[i : i + 2]
        if two == "**":
            tokens.append(Token(TokenKind.DOUBLESTAR, "**", line=line, col=col, length=2))
            i += 2
            continue
        if two == "<=":
            tokens.append(Token(TokenKind.LE, "<=", line=line, col=col, length=2))
            i += 2
            continue
        if two == ">=":
            tokens.append(Token(TokenKind.GE, ">=", line=line, col=col, length=2))
            i += 2
            continue
        if two == "==":
            tokens.append(Token(TokenKind.EQ, "==", line=line, col=col, length=2))
            i += 2
            continue
        if two == "!=":
            tokens.append(Token(TokenKind.NE, "!=", line=line, col=col, length=2))
            i += 2
            continue

        single_map: dict[str, TokenKind] = {
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.STAR,
            "/": TokenKind.SLASH,
            "%": TokenKind.PERCENT,
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            ",": TokenKind.COMMA,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
        }
        if ch in single_map:
            tokens.append(Token(single_map[ch], ch, line=line, col=col))
            i += 1
            continue

        raise LexError(f"unexpected character {ch!r}", line=line, col=col)

    tokens.append(Token(TokenKind.EOF, None, line=line, col=i - line_start + 1))
    return tokens
