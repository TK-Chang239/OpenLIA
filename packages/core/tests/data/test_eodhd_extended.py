"""Tests for openlia.data.eodhd_extended.ExtendedAPIClient.

We test against a fake `get_macro_indicators_data` because the live API
requires network + a paid key. The real-API smoke test is intentionally
out of scope here — covered by manual probing during the verification
pass.
"""

from __future__ import annotations

from typing import Any

import pytest


def _make_client(macro_payload: dict[tuple[str, str], list[dict[str, Any]]]):
    """Construct ExtendedAPIClient with a stub for both upstream calls."""
    from openlia.data.eodhd_extended import ExtendedAPIClient

    client = ExtendedAPIClient(api_key="demo")

    def fake_macro(country: str, indicator: str | None = None) -> list[dict[str, Any]]:
        return macro_payload[(country, indicator or "")]

    client.get_macro_indicators_data = fake_macro  # type: ignore[method-assign]
    return client


def test_debt_to_gdp_returns_latest_non_null_value() -> None:
    """debt_to_gdp() picks the most recent record with a non-null Value
    from EODHD's macro feed and returns it as a float."""
    client = _make_client(
        {
            ("USA", "debt_percent_gdp"): [
                {"Date": "2024-12-31", "Value": 122.4},
                {"Date": "2025-12-31", "Value": 124.0},
                {"Date": "2026-12-31", "Value": None},  # not-yet-released — must be skipped
            ],
        }
    )
    assert client.debt_to_gdp(country="US") == 124.0


def test_debt_to_gdp_iso2_country_is_translated_to_iso3() -> None:
    """Wrapper accepts iso-2 ('US') and forwards iso-3 ('USA') downstream."""
    seen: dict[str, str] = {}
    from openlia.data.eodhd_extended import ExtendedAPIClient

    client = ExtendedAPIClient(api_key="demo")

    def fake(country: str, indicator: str | None = None) -> list[dict[str, Any]]:
        seen["country"] = country
        seen["indicator"] = indicator or ""
        return [{"Date": "2025-01-01", "Value": 1.0}]

    client.get_macro_indicators_data = fake  # type: ignore[method-assign]
    client.debt_to_gdp(country="DE")
    assert seen == {"country": "DEU", "indicator": "debt_percent_gdp"}


def test_debt_to_gdp_raises_when_no_non_null_values() -> None:
    client = _make_client(
        {
            ("USA", "debt_percent_gdp"): [
                {"Date": "2026-12-31", "Value": None},
            ],
        }
    )
    with pytest.raises(RuntimeError, match="debt_percent_gdp"):
        client.debt_to_gdp(country="US")


def test_gdp_growth_yoy_picks_latest_non_null_value() -> None:
    client = _make_client(
        {
            ("USA", "gdp_growth_annual"): [
                {"Date": "2024-12-31", "Value": 2.5},
                {"Date": "2025-12-31", "Value": 2.8},
                {"Date": "2026-12-31", "Value": None},
            ],
        }
    )
    assert client.gdp_growth_yoy(country="US") == 2.8


def test_cpi_yoy_picks_latest_non_null_value() -> None:
    client = _make_client(
        {
            ("USA", "inflation_consumer_prices_annual"): [
                {"Date": "2025-12-31", "Value": 3.1},
                {"Date": "2024-12-31", "Value": 3.4},
            ],
        }
    )
    assert client.cpi_yoy(country="US") == 3.1
