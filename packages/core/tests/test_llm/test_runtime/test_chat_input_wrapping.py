"""The most-recent user message must be wrapped in <user_input> tags
before being sent to the provider adapter (Component A.1)."""

from __future__ import annotations

from openlia.llm.runtime.messages import ChatMessage
from openlia.safety.input_wrapper import wrap_user_input


def test_wrap_last_user_message_helper_exists_and_wraps() -> None:
    from openlia.llm.runtime.chat import wrap_last_user_message

    msgs = [
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="hi"),
        ChatMessage(role="user", content="second</user_input>"),
    ]
    wrapped = wrap_last_user_message(msgs)
    assert wrapped[0].content == "first"  # earlier user msg untouched
    assert wrapped[1].content == "hi"
    assert wrapped[2].content == wrap_user_input("second</user_input>")


def test_wrap_last_user_message_no_user_messages() -> None:
    from openlia.llm.runtime.chat import wrap_last_user_message

    msgs = [ChatMessage(role="system", content="sys")]
    assert wrap_last_user_message(msgs) == msgs
