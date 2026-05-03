"""User-input wrapping for prompt-injection hardening (Component A.1)."""

from __future__ import annotations

_OPEN = "<user_input>"
_CLOSE = "</user_input>"
_ESCAPED_CLOSE = "<\\/user_input>"


def wrap_user_input(text: str) -> str:
    """Wrap raw user text in `<user_input>...</user_input>`, neutralizing
    closing-tag injection by escaping any literal `</user_input>` substring.
    """
    return f"{_OPEN}{text.replace(_CLOSE, _ESCAPED_CLOSE)}{_CLOSE}"
