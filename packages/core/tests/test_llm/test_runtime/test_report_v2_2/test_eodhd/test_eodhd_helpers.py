"""Tests for the 18 EODHD adapter helpers.

Uses canned fixtures — no live API calls.
Live smoke test (requires EODHD_API_KEY + LIVE_EODHD_TESTS=1) at the bottom.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
    get_helper,
    list_helpers,
)

from . import fixtures as F

# ---------------------------------------------------------------------------
# Helper: patch _get so helpers never hit the network
# ---------------------------------------------------------------------------

_CLIENT_PATH = "openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd.client._get"


def _patch_get(return_value: Any):
    return patch(_CLIENT_PATH, return_value=return_value)


# ---------------------------------------------------------------------------
# Registration tests — all 18 helpers must be in the registry
# ---------------------------------------------------------------------------

EXPECTED_HELPERS = [
    "eodhd_fundamentals",
    "eodhd_balance_sheet",
    "eodhd_income_statement",
    "eodhd_cash_flow",
    "eodhd_eod_prices",
    "eodhd_intraday",
    "eodhd_real_time_quote",
    "eodhd_dividends",
    "eodhd_splits",
    "eodhd_market_cap_history",
    "eodhd_insider_transactions",
    "eodhd_news",
    "eodhd_sentiment",
    "eodhd_company_info",
    "eodhd_earnings_history",
    "eodhd_upcoming_earnings",
    "eodhd_technical_indicators",
    "eodhd_macro_indicator",
]


@pytest.mark.parametrize("name", EXPECTED_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


def test_all_18_eodhd_helpers_registered() -> None:
    registered = {h.schema.directory.name for h in list_helpers()}
    missing = [n for n in EXPECTED_HELPERS if n not in registered]
    assert not missing, f"Missing helpers: {missing}"


# ---------------------------------------------------------------------------
# eodhd_fundamentals
# ---------------------------------------------------------------------------


def test_fundamentals_returns_dict() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_fundamentals").impl(ticker="MSFT")
    assert isinstance(result, dict)
    assert "General" in result
    assert result["General"]["Code"] == "MSFT"


def test_fundamentals_exchange_suffix() -> None:
    calls: list[tuple] = []

    def fake_get(endpoint, uri="", querystring=""):
        calls.append((endpoint, uri))
        return F.MSFT_FUNDAMENTALS

    with patch(_CLIENT_PATH, side_effect=fake_get):
        get_helper("eodhd_fundamentals").impl(ticker="NESN", exchange="SW")

    assert calls[0][1] == "NESN.SW"


def test_fundamentals_ticker_with_dot_not_doubled() -> None:
    calls: list[tuple] = []

    def fake_get(endpoint, uri="", querystring=""):
        calls.append((endpoint, uri))
        return F.NESN_FUNDAMENTALS

    with patch(_CLIENT_PATH, side_effect=fake_get):
        get_helper("eodhd_fundamentals").impl(ticker="NESN.SW")

    assert calls[0][1] == "NESN.SW"


# ---------------------------------------------------------------------------
# eodhd_balance_sheet
# ---------------------------------------------------------------------------


def test_balance_sheet_quarterly() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_balance_sheet").impl(ticker="MSFT", period="quarterly")
    assert isinstance(result, dict)
    assert result["period"] == "quarterly"
    assert "statements" in result
    assert "2024-03-31" in result["statements"]


def test_balance_sheet_annual() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_balance_sheet").impl(ticker="MSFT", period="annual")
    assert result["period"] == "annual"
    assert "2023-06-30" in result["statements"]


# ---------------------------------------------------------------------------
# eodhd_income_statement
# ---------------------------------------------------------------------------


def test_income_statement_quarterly() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_income_statement").impl(ticker="MSFT")
    assert isinstance(result, dict)
    assert "statements" in result
    statements = result["statements"]
    assert "2024-03-31" in statements
    assert statements["2024-03-31"]["totalRevenue"] == 61858000000


# ---------------------------------------------------------------------------
# eodhd_cash_flow
# ---------------------------------------------------------------------------


def test_cash_flow_has_operating() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_cash_flow").impl(ticker="MSFT")
    assert "statements" in result
    row = result["statements"].get("2024-03-31", {})
    assert row.get("totalCashFromOperatingActivities") == 31900000000


# ---------------------------------------------------------------------------
# eodhd_eod_prices
# ---------------------------------------------------------------------------


def test_eod_prices_returns_rows_list() -> None:
    with _patch_get(F.MSFT_EOD_PRICES):
        result = get_helper("eodhd_eod_prices").impl(ticker="MSFT")
    assert isinstance(result, dict)
    assert isinstance(result["rows"], list)
    assert len(result["rows"]) == 3
    assert result["rows"][0]["date"] == "2024-01-02"


def test_eod_prices_non_list_response_wraps_empty() -> None:
    with _patch_get({"error": "not found"}):
        result = get_helper("eodhd_eod_prices").impl(ticker="FAKE")
    assert result["rows"] == []


# ---------------------------------------------------------------------------
# eodhd_intraday
# ---------------------------------------------------------------------------


def test_intraday_returns_rows() -> None:
    with _patch_get(F.MSFT_INTRADAY):
        result = get_helper("eodhd_intraday").impl(ticker="MSFT", interval="5m")
    assert isinstance(result["rows"], list)
    assert len(result["rows"]) == 2
    assert result["interval"] == "5m"


# ---------------------------------------------------------------------------
# eodhd_real_time_quote
# ---------------------------------------------------------------------------


def test_real_time_quote_has_close() -> None:
    with _patch_get(F.MSFT_REAL_TIME_QUOTE):
        result = get_helper("eodhd_real_time_quote").impl(ticker="MSFT")
    assert isinstance(result, dict)
    assert result["close"] == 421.44
    assert result["change_p"] == 1.118


def test_real_time_quote_list_response_wraps() -> None:
    with _patch_get([F.MSFT_REAL_TIME_QUOTE]):
        result = get_helper("eodhd_real_time_quote").impl(ticker="MSFT")
    assert "code" in result or "raw" in result


# ---------------------------------------------------------------------------
# eodhd_dividends
# ---------------------------------------------------------------------------


def test_dividends_returns_list() -> None:
    with _patch_get(F.MSFT_DIVIDENDS):
        result = get_helper("eodhd_dividends").impl(ticker="MSFT")
    assert isinstance(result["dividends"], list)
    assert result["dividends"][0]["value"] == 0.75


# ---------------------------------------------------------------------------
# eodhd_splits
# ---------------------------------------------------------------------------


def test_splits_returns_list() -> None:
    with _patch_get(F.MSFT_SPLITS):
        result = get_helper("eodhd_splits").impl(ticker="MSFT")
    assert isinstance(result["splits"], list)
    assert result["splits"][0]["split"] == "2/1"


# ---------------------------------------------------------------------------
# eodhd_market_cap_history
# ---------------------------------------------------------------------------


def test_market_cap_history_returns_list() -> None:
    with _patch_get(F.MSFT_MARKET_CAP_HISTORY):
        result = get_helper("eodhd_market_cap_history").impl(ticker="MSFT")
    assert isinstance(result["market_cap_history"], list)
    assert result["market_cap_history"][0]["marketCapitalization"] == 3050000000000


# ---------------------------------------------------------------------------
# eodhd_insider_transactions
# ---------------------------------------------------------------------------


def test_insider_transactions_returns_list() -> None:
    with _patch_get(F.MSFT_INSIDER_TRANSACTIONS):
        result = get_helper("eodhd_insider_transactions").impl(ticker="MSFT")
    assert isinstance(result["transactions"], list)
    assert result["transactions"][0]["ownerName"] == "Nadella Satya"


def test_insider_transactions_ticker_in_querystring() -> None:
    calls: list[dict] = []

    def fake_get(endpoint="", uri="", querystring=""):
        calls.append({"endpoint": endpoint, "uri": uri, "qs": querystring})
        return F.MSFT_INSIDER_TRANSACTIONS

    with patch(_CLIENT_PATH, side_effect=fake_get):
        get_helper("eodhd_insider_transactions").impl(ticker="MSFT")

    assert "MSFT.US" in calls[0]["qs"]


# ---------------------------------------------------------------------------
# eodhd_news
# ---------------------------------------------------------------------------


def test_news_returns_articles() -> None:
    with _patch_get(F.MSFT_NEWS):
        result = get_helper("eodhd_news").impl(ticker="MSFT")
    assert isinstance(result["articles"], list)
    assert len(result["articles"]) == 2
    assert "Microsoft" in result["articles"][0]["title"]


# ---------------------------------------------------------------------------
# eodhd_sentiment
# ---------------------------------------------------------------------------


def test_sentiment_returns_data() -> None:
    with _patch_get(F.MSFT_SENTIMENT):
        result = get_helper("eodhd_sentiment").impl(ticker="MSFT")
    assert isinstance(result["sentiment"], dict)
    assert "MSFT.US" in result["sentiment"]


# ---------------------------------------------------------------------------
# eodhd_company_info
# ---------------------------------------------------------------------------


def test_company_info_sector() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_company_info").impl(ticker="MSFT")
    assert result["general"]["Sector"] == "Technology"
    assert result["general"]["Name"] == "Microsoft Corp"


def test_company_info_nesn() -> None:
    with _patch_get(F.NESN_FUNDAMENTALS):
        result = get_helper("eodhd_company_info").impl(ticker="NESN", exchange="SW")
    assert result["general"]["CountryISO"] == "CH"


# ---------------------------------------------------------------------------
# eodhd_earnings_history
# ---------------------------------------------------------------------------


def test_earnings_history_has_quarters() -> None:
    with _patch_get(F.MSFT_FUNDAMENTALS):
        result = get_helper("eodhd_earnings_history").impl(ticker="MSFT")
    assert "quarterly_history" in result
    assert "2024-03-31" in result["quarterly_history"]
    assert result["quarterly_history"]["2024-03-31"]["epsActual"] == 2.94


# ---------------------------------------------------------------------------
# eodhd_upcoming_earnings
# ---------------------------------------------------------------------------


def test_upcoming_earnings_returns_list() -> None:
    with _patch_get(F.MSFT_UPCOMING_EARNINGS):
        result = get_helper("eodhd_upcoming_earnings").impl(ticker="MSFT")
    assert isinstance(result["upcoming_earnings"], list)
    assert result["upcoming_earnings"][0]["estimate"] == 3.01


def test_upcoming_earnings_list_response() -> None:
    # API may return a list directly
    with _patch_get([F.MSFT_UPCOMING_EARNINGS["earnings"][0]]):
        result = get_helper("eodhd_upcoming_earnings").impl(ticker="MSFT")
    assert isinstance(result["upcoming_earnings"], list)


# ---------------------------------------------------------------------------
# eodhd_technical_indicators
# ---------------------------------------------------------------------------


def test_technical_indicators_rsi() -> None:
    with _patch_get(F.MSFT_RSI):
        result = get_helper("eodhd_technical_indicators").impl(
            ticker="MSFT", function="rsi", period=14
        )
    assert result["function"] == "rsi"
    assert result["period"] == 14
    assert isinstance(result["rows"], list)
    assert result["rows"][0]["rsi"] == 58.32


def test_technical_indicators_invalid_function() -> None:
    with pytest.raises(ValueError, match="Unknown technical indicator"):
        get_helper("eodhd_technical_indicators").impl(ticker="MSFT", function="not_a_real_function")


# ---------------------------------------------------------------------------
# eodhd_macro_indicator
# ---------------------------------------------------------------------------


def test_macro_indicator_gdp() -> None:
    with _patch_get(F.USA_GDP):
        result = get_helper("eodhd_macro_indicator").impl(
            country="USA", indicator="gdp_current_usd"
        )
    assert result["country"] == "USA"
    assert result["indicator"] == "gdp_current_usd"
    assert isinstance(result["series"], list)
    assert result["series"][0]["value"] == 27360000000000.0


# ---------------------------------------------------------------------------
# Schema integrity tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", EXPECTED_HELPERS)
def test_helper_schema_has_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert len(helper.schema.contract.produces_artifacts) == 1
    artifact = helper.schema.contract.produces_artifacts[0]
    assert artifact.endswith("_output"), f"{name}: artifact {artifact!r} should end with '_output'"


@pytest.mark.parametrize("name", EXPECTED_HELPERS)
def test_helper_schema_category_is_adapter(name: str) -> None:
    from openlia.llm.runtime.report_v2_2 import Category

    helper = get_helper(name)
    assert helper.schema.directory.category == Category.ADAPTER


@pytest.mark.parametrize("name", EXPECTED_HELPERS)
def test_helper_schema_version(name: str) -> None:
    helper = get_helper(name)
    assert helper.schema.version == "0.1.0"


# ---------------------------------------------------------------------------
# Client unit tests (no network)
# ---------------------------------------------------------------------------


def test_client_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd.client import get_api_key

    with pytest.raises(RuntimeError, match="EODHD_API_KEY"):
        get_api_key()


def test_client_returns_key_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODHD_API_KEY", "demo1234567890ab")
    from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd.client import get_api_key

    assert get_api_key() == "demo1234567890ab"


def test_client_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _get retries on 429 and succeeds on 3rd attempt."""
    monkeypatch.setenv("EODHD_API_KEY", "demo1234567890ab")

    import requests as req_mod
    from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd import client as client_mod

    call_count = 0

    class FakeResponse:
        def __init__(self, status: int, body: Any = None) -> None:
            self.status_code = status
            self._body = body or {}

        def json(self) -> Any:
            return self._body

        def raise_for_status(self) -> None:
            if self.status_code != 200:
                raise req_mod.HTTPError(response=self)

    def fake_requests_get(url: str, timeout: int = 30) -> FakeResponse:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return FakeResponse(429)
        return FakeResponse(200, {"result": "ok"})

    # Patch sleep to avoid actual waiting
    with patch.object(client_mod, "time") as mock_time:
        mock_time.sleep = lambda _: None
        with patch.object(client_mod, "requests") as mock_req:
            mock_req.get = fake_requests_get
            mock_req.RequestException = req_mod.RequestException
            result = client_mod._get("eod", "MSFT.US")

    assert result == {"result": "ok"}
    assert call_count == 3


def test_client_raises_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODHD_API_KEY", "demo1234567890ab")

    import requests as req_mod
    from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd import client as client_mod

    class FakeResponse:
        status_code = 429

        def json(self) -> dict:
            return {}

    with patch.object(client_mod, "time") as mock_time:
        mock_time.sleep = lambda _: None
        with patch.object(client_mod, "requests") as mock_req:
            mock_req.get = lambda url, timeout=30: FakeResponse()
            mock_req.RequestException = req_mod.RequestException
            with pytest.raises(RuntimeError, match="rate-limit"):
                client_mod._get("eod", "MSFT.US")


def test_client_raises_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODHD_API_KEY", "demo1234567890ab")

    import requests as req_mod
    from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd import client as client_mod

    class FakeResponse:
        status_code = 403

        def json(self) -> dict:
            return {"message": "Forbidden"}

    with patch.object(client_mod, "requests") as mock_req:
        mock_req.get = lambda url, timeout=30: FakeResponse()
        mock_req.RequestException = req_mod.RequestException
        with pytest.raises(RuntimeError, match="403"):
            client_mod._get("fundamentals", "FAKE.US")


# ---------------------------------------------------------------------------
# Integration smoke test (live API — skipped unless explicitly opted in)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (os.environ.get("EODHD_API_KEY") and os.environ.get("LIVE_EODHD_TESTS") == "1"),
    reason="Live EODHD tests require EODHD_API_KEY and LIVE_EODHD_TESTS=1",
)
def test_live_msft_fundamentals() -> None:
    result = get_helper("eodhd_fundamentals").impl(ticker="MSFT")
    assert isinstance(result, dict)
    assert "General" in result
    assert result["General"]["Code"] == "MSFT"


@pytest.mark.skipif(
    not (os.environ.get("EODHD_API_KEY") and os.environ.get("LIVE_EODHD_TESTS") == "1"),
    reason="Live EODHD tests require EODHD_API_KEY and LIVE_EODHD_TESTS=1",
)
def test_live_nesn_sw_fundamentals() -> None:
    result = get_helper("eodhd_fundamentals").impl(ticker="NESN", exchange="SW")
    assert isinstance(result, dict)
    assert "General" in result
