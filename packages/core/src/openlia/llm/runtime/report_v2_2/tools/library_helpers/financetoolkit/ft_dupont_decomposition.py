"""ft_dupont_decomposition — 3-step DuPont decomposition via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.models.dupont_model as _dup
import pandas as pd

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

_PERIOD_LABEL = "2024"


def execute(
    net_income: float,
    total_revenue: float,
    total_assets: float,
    total_equity: float,
) -> dict[str, Any]:
    """Compute 3-step DuPont decomposition.

    The DuPont model breaks ROE into:
      Net Profit Margin x Asset Turnover x Equity Multiplier = ROE

    Args:
        net_income: Net income.
        total_revenue: Total revenue.
        total_assets: Total assets (used as both average start and end value).
        total_equity: Total shareholder equity (used as both average start and end value).

    Returns:
        Dict with each DuPont component and the implied ROE.
    """
    net_income_s = pd.Series([net_income], index=[_PERIOD_LABEL], name="MSFT")
    revenue_s = pd.Series([total_revenue], index=[_PERIOD_LABEL], name="MSFT")
    assets_s = pd.Series([total_assets], index=[_PERIOD_LABEL], name="MSFT")
    equity_s = pd.Series([total_equity], index=[_PERIOD_LABEL], name="MSFT")

    result = _dup.get_dupont_analysis(
        net_income=net_income_s,
        total_revenue=revenue_s,
        average_total_assets=assets_s,
        average_total_equity=equity_s,
    )

    # result is a DataFrame: rows = components, columns = period labels
    # e.g.:
    #                     2024
    # Net Profit Margin    0.1
    # Asset Turnover       2.0
    # Equity Multiplier    2.0
    # Return on Equity     0.4
    if isinstance(result, pd.DataFrame):
        # Transpose so we get {component_name: value} for the single period
        flat: dict[str, float | None] = {}
        for idx, row in result.iterrows():
            vals = row.dropna().tolist()
            flat[str(idx).lower().replace(" ", "_")] = float(vals[0]) if vals else None
        return flat
    elif isinstance(result, pd.Series):
        return {str(k).lower().replace(" ", "_"): float(v) for k, v in result.items()}
    else:
        return {"error": "Unexpected result type from dupont_model"}


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_dupont_decomposition",
        category=Category.BUSINESS_QUALITY,
        one_liner="3-step DuPont: net margin, asset turnover, equity multiplier → ROE.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Decompose ROE into its three DuPont drivers using FinanceToolkit's DuPont model "
            "applied to user-supplied income statement and balance sheet scalars."
        ),
        when_to_use=[
            "Understanding the source of ROE (profitability vs. efficiency vs. leverage).",
            "Peer comparison of ROE drivers for an equity research quality section.",
        ],
        when_not_to_use=[
            "Full 5-step extended DuPont — not yet implemented in v2.2 (planned PR 2.7).",
            "Profitability ratios standalone — use ft_profitability_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(
                type="float",
                required=True,
                description="Net income.",
            ),
            "total_revenue": HelperParam(
                type="float",
                required=True,
                description="Total revenue.",
            ),
            "total_assets": HelperParam(
                type="float",
                required=True,
                description="Total assets.",
            ),
            "total_equity": HelperParam(
                type="float",
                required=True,
                description="Total shareholder equity.",
            ),
        },
        outputs=[
            HelperOutput(
                name="dupont_components",
                type="dict",
                description=(
                    "Dict with net_profit_margin, asset_turnover, equity_multiplier, "
                    "return_on_equity."
                ),
            ),
        ],
        produces_artifacts=["ft_dupont_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
