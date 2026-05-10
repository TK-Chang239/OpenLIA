from __future__ import annotations

import pytest
from openlia.llm.runtime.messages import (
    Attachment,
    BatchItem,
    BatchResult,
    ChatMessage,
    ReportRequest,
)


def test_chat_message_basic() -> None:
    m = ChatMessage(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"
    assert m.attachments == []


def test_chat_message_roles_are_open_strings() -> None:
    assert ChatMessage(role="assistant", content="hi").role == "assistant"
    assert ChatMessage(role="system", content="be nice").role == "system"


def test_chat_message_with_attachments_carries_runtime_attachment() -> None:
    a = Attachment(
        id="att-1",
        filename="a.png",
        mime_type="image/png",
        storage_path="/tmp/a.png",
        size_bytes=12,
    )
    m = ChatMessage(role="user", content="see this", attachments=[a])
    assert m.attachments[0].filename == "a.png"
    assert m.attachments[0].mime_type == "image/png"
    assert m.attachments[0].storage_path == "/tmp/a.png"


def test_report_request_minimal() -> None:
    r = ReportRequest(
        mode="stock_initiation",
        user_input="Initiate AAPL.",
    )
    assert r.mode == "stock_initiation"
    assert r.user_input == "Initiate AAPL."
    assert r.enabled_sections == []
    assert r.custom_sections == []
    assert r.length == "standard"


def test_report_request_full() -> None:
    r = ReportRequest(
        mode="sector_research",
        user_input="US semis.",
        enabled_sections=["overview", "thesis"],
        custom_sections=[{"title": "Regulatory outlook", "instructions": "US-only."}],
        length="long",
    )
    assert r.enabled_sections == ["overview", "thesis"]
    assert r.custom_sections[0]["title"] == "Regulatory outlook"
    assert r.length == "long"


def test_report_request_rejects_unknown_length() -> None:
    with pytest.raises(ValueError, match="length"):
        ReportRequest(mode="stock_update", user_input="AAPL", length="gargantuan")


def test_batch_item_shape() -> None:
    item = BatchItem(id="post-1", context={"text": "YOLO AAPL calls"})
    assert item.id == "post-1"
    assert item.context["text"] == "YOLO AAPL calls"


def test_batch_result_ok() -> None:
    r = BatchResult(id="post-1", ok=True, data={"sentiment": "bullish"}, error=None)
    assert r.ok is True
    assert r.data == {"sentiment": "bullish"}
    assert r.error is None


def test_batch_result_failure_carries_error() -> None:
    r = BatchResult(id="post-2", ok=False, data=None, error="ContextLengthError: 8192")
    assert r.ok is False
    assert r.data is None
    assert r.error == "ContextLengthError: 8192"
