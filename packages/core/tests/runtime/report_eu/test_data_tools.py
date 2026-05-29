from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.tools.data_tools import build_earnings_calendar_tool


def test_earnings_calendar_tool_calls_transport_and_logs():
    ledger = CitationLedger()
    calls: list[str] = []

    def transport(ticker: str) -> list[dict]:
        calls.append(ticker)
        return [{"report_date": "2026-06-15", "estimate": "2.50"}]

    tool = build_earnings_calendar_tool(ledger=ledger, earnings_calendar=transport)
    result = tool.execute({"ticker": "MSFT.US"})

    assert calls == ["MSFT.US"]
    assert "2026-06-15" in str(result.payload)
    assert tool.descriptor.name == "get_earnings_calendar"
    # The call landed one ledger entry the model can cite.
    assert result.payload["source_id"].startswith("get_earnings_calendar")
    assert ledger.lookup(result.payload["source_id"]) is not None
