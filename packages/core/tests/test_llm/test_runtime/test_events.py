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
        error_class="ModelNotConfiguredError",
        message="No model is configured for department='equity_research'.",
    )
    d = to_wire(e)
    assert d["type"] == "chat.error"
    assert d["error_class"] == "ModelNotConfiguredError"
    assert "equity_research" in d["message"]


def test_chat_report_thumbnail_links_report_id() -> None:
    # NEW-5-01: `mode` is the canonical field; `filename` retained for FE
    # backwards compatibility (deprecated).
    e = ChatReportThumbnail(
        message_id="m_1",
        report_id="r_1",
        mode="stock_initiation",
        filename="report.pdf",
    )
    wire = to_wire(e)
    assert wire["type"] == "chat.report_thumbnail"
    assert wire["message_id"] == "m_1"
    assert wire["report_id"] == "r_1"
    assert wire["mode"] == "stock_initiation"
    assert wire["filename"] == "report.pdf"


def test_chat_report_thumbnail_filename_optional_for_backwards_compat() -> None:
    # `filename` defaults to "" so callers can omit it.
    e = ChatReportThumbnail(message_id="m_1", report_id="r_1", mode="earnings_update")
    wire = to_wire(e)
    assert wire["mode"] == "earnings_update"
    assert wire["filename"] == ""


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
    wire = to_wire(e)
    assert wire["type"] == "report.error"
    assert wire["report_id"] == "r_1"
    assert wire["error_class"] == "CapabilityError"
    assert wire["message"] == "Tools not supported"
    # P2-NEW-5-07: terminal events carry an ISO-8601 UTC timestamp.
    assert "ts" in wire
    assert wire["ts"].endswith("+00:00") or wire["ts"].endswith("Z")


def test_to_wire_output_is_json_serializable() -> None:
    e = ReportComplete(report_id="r_1", schema={"title": "x", "sections": []})
    json.dumps(to_wire(e))  # must not raise


def test_report_tool_call_carries_call_id() -> None:
    """NEW-5-02: ReportToolCall carries call_id so the FE can correlate it
    with a preceding report.tool_call.start event."""
    e = ReportToolCall(
        report_id="r_1",
        tool_name="financial_statements",
        summary="Fetched 10-K",
        call_id="c_42",
    )
    wire = to_wire(e)
    assert wire["call_id"] == "c_42"


def test_report_tool_call_start_wire_shape() -> None:
    """NEW-5-03: report.tool_call.start fired before dispatch carries call_id,
    tool_name, and an args preview."""
    from openlia.llm.runtime.events import ReportToolCallStart

    e = ReportToolCallStart(
        report_id="r_1",
        call_id="c_42",
        tool_name="stock_quote",
        args_preview='{"symbol":"AAPL"}',
    )
    wire = to_wire(e)
    assert wire["type"] == "report.tool_call.start"
    assert wire["call_id"] == "c_42"
    assert wire["tool_name"] == "stock_quote"
    assert wire["args_preview"] == '{"symbol":"AAPL"}'


def test_chat_done_includes_ts() -> None:
    """P2-NEW-5-07: terminal ChatDone carries ISO-8601 UTC ts."""
    e = ChatDone(message_id="m_1", stop_reason="complete")
    wire = to_wire(e)
    assert "ts" in wire
    # ISO-8601 UTC ends with +00:00 (Python's datetime.isoformat) or Z.
    assert wire["ts"].endswith("+00:00") or wire["ts"].endswith("Z")


def test_chat_error_includes_ts() -> None:
    e = ChatError(message_id="m_1", error_class="X", message="y")
    wire = to_wire(e)
    assert "ts" in wire


def test_report_complete_includes_ts() -> None:
    e = ReportComplete(report_id="r_1", schema={})
    wire = to_wire(e)
    assert "ts" in wire
