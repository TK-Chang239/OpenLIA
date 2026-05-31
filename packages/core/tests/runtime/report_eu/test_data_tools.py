from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.tools.data_tools import (
    build_data_tools,
    build_earnings_calendar_tool,
)


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


def test_earnings_calendar_prunes_event_fields_but_keeps_empty_list_signal():
    ledger = CitationLedger()

    def with_events(_ticker: str) -> list[dict]:
        return [{"report_date": "2026-06-15", "estimate": None, "currency": ""}]

    tool = build_earnings_calendar_tool(ledger=ledger, earnings_calendar=with_events)
    payload = tool.execute({"ticker": "MSFT.US"}).payload
    # Null/blank event fields are pruned; the real field survives.
    assert payload["data"]["upcoming_earnings"] == [{"report_date": "2026-06-15"}]

    def no_events(_ticker: str) -> list[dict]:
        return []

    empty_tool = build_earnings_calendar_tool(ledger=ledger, earnings_calendar=no_events)
    empty_payload = empty_tool.execute({"ticker": "MSFT.US"}).payload
    # An empty list is a meaningful "no upcoming releases" signal — the
    # key must remain present, not be dropped as noise.
    assert empty_payload["data"]["upcoming_earnings"] == []


def test_fundamentals_data_payload_is_pruned_of_empty_fields():
    ledger = CitationLedger()

    def fundamentals(_ticker: str) -> dict:
        return {
            "Highlights": {"MarketCap": 1000, "Beta": None, "Note": ""},
            "Empty": {},
        }

    def prices(_ticker: str, _from: str, _to: str) -> list[dict]:
        return []

    def news(_ticker: str, _limit: int) -> list[dict]:
        return []

    tools = build_data_tools(ledger=ledger, fundamentals=fundamentals, prices=prices, news=news)
    fundamentals_tool = next(t for t in tools if t.descriptor.name == "get_fundamentals")
    data = fundamentals_tool.execute({"ticker": "MSFT.US"}).payload["data"]

    assert data == {"Highlights": {"MarketCap": 1000}}
