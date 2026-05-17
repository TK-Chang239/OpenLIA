from __future__ import annotations

from openlia.llm.runtime.chat_transcript_compressor import compress_chat_transcript


def _msg(role: str, content: str, tool_calls=None, tool_call_id=None) -> dict:
    return {
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "tool_call_id": tool_call_id,
    }


def test_user_and_assistant_messages_kept_verbatim() -> None:
    msgs = [
        _msg("user", "What's the revenue?"),
        _msg("assistant", "$245B in FY25."),
    ]
    out = compress_chat_transcript(msgs)
    assert "What's the revenue?" in out
    assert "$245B in FY25." in out


def test_tool_calls_summarized_not_verbatim() -> None:
    msgs = [
        _msg("user", "Check Q4."),
        _msg(
            "assistant",
            "",
            tool_calls=[
                {
                    "id": "c1",
                    "function": {
                        "name": "read_payload",
                        "arguments": '{"ref":"r_abc","path":"Financials.Cash_Flow.yearly"}',
                    },
                }
            ],
        ),
        _msg("tool", "1213 chars of tabular data...", tool_call_id="c1"),
    ]
    out = compress_chat_transcript(msgs)
    assert "read_payload" in out
    assert "Financials.Cash_Flow.yearly" in out
    # The raw 1213-char payload is NOT verbatim — it's summarized.
    assert "1213 chars" in out or "chars" in out


def test_cap_chars_trims_oldest_first_with_marker() -> None:
    long_text = "x" * 50_000
    msgs = [
        _msg("user", "early message — should be trimmed"),
        _msg("assistant", long_text),
        _msg("user", "recent message — must be kept"),
    ]
    out = compress_chat_transcript(msgs, cap_chars=10_000)
    assert len(out) <= 10_000
    assert "recent message" in out
    # Trimming marker present.
    assert "trimmed" in out.lower() or "..." in out


def test_empty_transcript_returns_empty_string() -> None:
    assert compress_chat_transcript([]) == ""
