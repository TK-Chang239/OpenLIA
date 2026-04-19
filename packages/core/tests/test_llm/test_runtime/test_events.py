from __future__ import annotations

import json

import pytest

from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatReportThumbnail,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
    to_wire,
)


def test_chat_start_wire_shape() -> None:
    e = ChatStart(message_id="m_1")
    assert to_wire(e) == {"type": "chat.start", "message_id": "m_1"}


def test_chat_token_wire_shape() -> None:
    e = ChatToken(message_id="m_1", text="Apple")
    assert to_wire(e) == {"type": "chat.token", "message_id": "m_1", "text": "Apple"}


def test_chat_tool_call_start_carries_preview() -> None:
    e = ChatToolCallStart(
        message_id="m_1",
        call_id="c_1",
        tool_name="stock_quote",
        args_preview='{"symbol":"AAPL"}',
    )
    d = to_wire(e)
    assert d["type"] == "chat.tool_call.start"
    assert d["call_id"] == "c_1"
    assert d["tool_name"] == "stock_quote"
    assert d["args_preview"] == '{"symbol":"AAPL"}'


def test_chat_tool_call_result_carries_ok_and_summary() -> None:
    e = ChatToolCallResult(
        message_id="m_1", call_id="c_1", ok=True, summary="Fetched quote for AAPL"
    )
    d = to_wire(e)
    assert d["type"] == "chat.tool_call.result"
    assert d["ok"] is True
    assert d["summary"] == "Fetched quote for AAPL"


def test_chat_done_carries_stop_reason() -> None:
    e = ChatDone(message_id="m_1", stop_reason="complete")
    assert to_wire(e)["stop_reason"] == "complete"


def test_chat_error_includes_class_and_message() -> None:
    e = ChatError(
        message_id="m_1",
        error_class="TierNotConfiguredError",
        message="No enabled models configured in tier 'thinking'.",
    )
    d = to_wire(e)
    assert d["type"] == "chat.error"
    assert d["error_class"] == "TierNotConfiguredError"
    assert "thinking" in d["message"]


def test_chat_report_thumbnail_links_report_id() -> None:
    e = ChatReportThumbnail(message_id="m_1", report_id="r_1", mode="stock_initiation")
    assert to_wire(e) == {
        "type": "chat.report_thumbnail",
        "message_id": "m_1",
        "report_id": "r_1",
        "mode": "stock_initiation",
    }


def test_report_start_includes_section_titles() -> None:
    e = ReportStart(
        report_id="r_1",
        department="equity_research",
        mode="stock_initiation",
        section_titles=["Overview", "Thesis"],
    )
    assert to_wire(e)["section_titles"] == ["Overview", "Thesis"]


def test_report_phase_values() -> None:
    assert to_wire(ReportPhase(report_id="r_1", phase="fetching_data"))["phase"] == "fetching_data"
    assert to_wire(ReportPhase(report_id="r_1", phase="writing"))["phase"] == "writing"
    assert to_wire(ReportPhase(report_id="r_1", phase="finalizing"))["phase"] == "finalizing"


def test_report_phase_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError, match="phase"):
        ReportPhase(report_id="r_1", phase="blasting_off")


def test_report_tool_call_wire_shape() -> None:
    e = ReportToolCall(
        report_id="r_1", tool_name="financial_statements", summary="Fetched 10-K for AAPL"
    )
    d = to_wire(e)
    assert d["type"] == "report.tool_call"
    assert d["tool_name"] == "financial_statements"


def test_report_complete_carries_schema_payload() -> None:
    schema = {"title": "AAPL Initiation", "sections": []}
    e = ReportComplete(report_id="r_1", schema=schema)
    d = to_wire(e)
    assert d["type"] == "report.complete"
    assert d["schema"] == schema


def test_report_error_wire_shape() -> None:
    e = ReportError(report_id="r_1", error_class="CapabilityError", message="Tools not supported")
    assert to_wire(e) == {
        "type": "report.error",
        "report_id": "r_1",
        "error_class": "CapabilityError",
        "message": "Tools not supported",
    }


def test_to_wire_output_is_json_serializable() -> None:
    e = ReportComplete(report_id="r_1", schema={"title": "x", "sections": []})
    json.dumps(to_wire(e))  # must not raise
