"""currency_neutral_growth — Constant-currency revenue growth vs reported.

Registered name: "currency_neutral_growth"
"""

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


def execute(
    reported_growth_pct: float,
    fx_impact_pct: float,
) -> dict[str, Any]:
    """Compute constant-currency (currency-neutral) revenue growth.

    Constant-currency growth = reported_growth - fx_impact.
    A positive fx_impact means FX was a tailwind (inflated reported growth).
    A negative fx_impact means FX was a headwind (suppressed reported growth).

    Args:
        reported_growth_pct: Reported revenue growth as percentage (e.g. 10.0 for 10%).
        fx_impact_pct: FX contribution to reported growth in percentage points.
            Positive = tailwind (FX boosted reported growth).
            Negative = headwind (FX dragged reported growth).

    Returns:
        Dict with reported growth, FX impact, constant-currency growth, and characterization.
    """
    cc_growth = reported_growth_pct - fx_impact_pct

    if fx_impact_pct > 0.5:
        fx_characterization = "tailwind"
    elif fx_impact_pct < -0.5:
        fx_characterization = "headwind"
    else:
        fx_characterization = "neutral"

    return {
        "reported_growth_pct": round(reported_growth_pct, 2),
        "fx_impact_pct": round(fx_impact_pct, 2),
        "constant_currency_growth_pct": round(cc_growth, 2),
        "fx_characterization": fx_characterization,
        "fx_magnitude_bps": round(fx_impact_pct * 100, 0),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="currency_neutral_growth",
        category=Category.BUSINESS_QUALITY,
        one_liner="Reported vs constant-currency revenue growth; FX headwind/tailwind.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Strip out FX to derive constant-currency (CC) revenue growth. "
            "FX tailwind inflates reported growth; headwind suppresses it."
        ),
        when_to_use=[
            "Multinational companies with material FX exposure.",
            "When management discloses CC growth and you want to reconcile to reported.",
        ],
        when_not_to_use=[
            "Organic vs M&A decomposition — use organic_vs_inorganic_growth.",
            "Full growth rate analysis — use ft_growth_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "reported_growth_pct": HelperParam(
                type="float",
                required=True,
                description="Reported revenue growth as percentage (e.g. 10.0 for 10%).",
            ),
            "fx_impact_pct": HelperParam(
                type="float",
                required=True,
                description=(
                    "FX contribution in pct points. Positive = tailwind, negative = headwind."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="currency_neutral_growth",
                type="dict",
                description=(
                    "reported_growth_pct, fx_impact_pct, constant_currency_growth_pct, "
                    "fx_characterization, fx_magnitude_bps."
                ),
            ),
        ],
        produces_artifacts=["currency_neutral_growth_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
