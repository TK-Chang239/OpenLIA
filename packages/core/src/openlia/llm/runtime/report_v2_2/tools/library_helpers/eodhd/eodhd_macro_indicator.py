"""eodhd_macro_indicator — macroeconomic indicator series for a country."""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

from . import client


def execute(
    country: str,
    indicator: str = "gdp_current_usd",
) -> dict[str, Any]:
    qs = f"&indicator={indicator}"
    rows = client._get("macro-indicator", country, qs)
    return {
        "country": country,
        "indicator": indicator,
        "series": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_macro_indicator",
        category=Category.ADAPTER,
        one_liner="EODHD macroeconomic indicator series (GDP, CPI, unemployment, etc.).",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch a macroeconomic time series from EODHD for a country. "
            "Supports indicators: gdp_current_usd, inflation_consumer_prices_annual, "
            "unemployment, real_interest_rate, and many others. "
            "Country code in Alpha-3 ISO format (USA, GBR, DEU, CHE, etc.)."
        ),
        when_to_use=[
            "Adding macro context (GDP growth, inflation) to an equity report.",
            "Country-level risk assessment for an emerging-market ticker.",
        ],
        when_not_to_use=[
            "Need company-level data — use any eodhd_fundamentals-based helper.",
            "Need economic events calendar — not this endpoint (see EODHD economic events API).",
        ],
    ),
    contract=MechanicalContract(
        params={
            "country": HelperParam(
                type="str",
                required=True,
                description="ISO Alpha-3 country code, e.g. 'USA', 'GBR', 'CHE'.",
            ),
            "indicator": HelperParam(
                type="str",
                required=False,
                default="gdp_current_usd",
                description=(
                    "Macro indicator key. Common values: gdp_current_usd, "
                    "inflation_consumer_prices_annual, unemployment, "
                    "real_interest_rate, real_gdp_growth. "
                    "Full list at https://eodhd.com/financial-apis/macroeconomics-data-and-macro-indicators-api/"
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description=(
                    "Dict with country, indicator, and series list of {date, value} records."
                ),
            ),
        ],
        produces_artifacts=["eodhd_macro_indicator_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.macro-indicator"],
    ),
)

register_helper(_SCHEMA, execute)
