"""altman_z_variants — Altman Z-score in all four published variants.

Registered name: "altman_z_variants"

Four variants:
  Z  (public manufacturer, Altman 1968): 5-factor model with market value equity
  Z' (private manufacturer, Altman 1983): replaces MVE with book equity
  Z" (non-manufacturer, Altman 1995): 4 factors; drops Sales/TA
  EM Z" (emerging markets): Z" + 3.25 constant for sovereign overlay

Per supplement §8.
"""

from __future__ import annotations

from typing import Any, Literal

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Variant definitions
# ---------------------------------------------------------------------------

_VARIANTS: dict[str, dict[str, Any]] = {
    "z": {
        "weights": {
            "working_capital_to_ta": 1.2,
            "retained_earnings_to_ta": 1.4,
            "ebit_to_ta": 3.3,
            "equity_to_liabilities": 0.6,  # MVE / BV_TL
            "sales_to_ta": 1.0,
        },
        "uses_market_equity": True,
        "uses_sales": True,
        "constant": 0.0,
        "thresholds": {"distress": 1.81, "gray_upper": 2.99},
    },
    "z_prime": {
        "weights": {
            "working_capital_to_ta": 0.717,
            "retained_earnings_to_ta": 0.847,
            "ebit_to_ta": 3.107,
            "equity_to_liabilities": 0.420,  # BVE / BV_TL
            "sales_to_ta": 0.998,
        },
        "uses_market_equity": False,
        "uses_sales": True,
        "constant": 0.0,
        "thresholds": {"distress": 1.23, "gray_upper": 2.90},
    },
    "z_double_prime": {
        "weights": {
            "working_capital_to_ta": 6.56,
            "retained_earnings_to_ta": 3.26,
            "ebit_to_ta": 6.72,
            "equity_to_liabilities": 1.05,  # BVE / BV_TL
        },
        "uses_market_equity": False,
        "uses_sales": False,
        "constant": 0.0,
        "thresholds": {"distress": 1.10, "gray_upper": 2.60},
    },
    "em_z_double_prime": {
        "weights": {
            "working_capital_to_ta": 6.56,
            "retained_earnings_to_ta": 3.26,
            "ebit_to_ta": 6.72,
            "equity_to_liabilities": 1.05,  # BVE / BV_TL
        },
        "uses_market_equity": False,
        "uses_sales": False,
        "constant": 3.25,
        "thresholds": {"distress": 4.35, "gray_upper": 5.85},
    },
}


def _classify(score: float, thresholds: dict[str, float]) -> str:
    if score < thresholds["distress"]:
        return "distress"
    if score <= thresholds["gray_upper"]:
        return "gray"
    return "safe"


def _compute_variant(
    variant_name: str,
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    market_value_equity: float | None,
    book_value_equity: float,
    book_value_total_liabilities: float,
    sales: float | None,
    total_assets: float,
) -> dict[str, Any]:
    """Compute a single Altman variant. Raises ValueError on structural violations."""
    if total_assets == 0:
        raise ValueError("total_assets must be non-zero")
    if book_value_total_liabilities == 0:
        raise ValueError(
            "book_value_total_liabilities must be non-zero for equity/liabilities ratio"
        )

    spec = _VARIANTS[variant_name]
    weights = spec["weights"]

    # Build ratios
    ratios: dict[str, float] = {
        "working_capital_to_ta": working_capital / total_assets,
        "retained_earnings_to_ta": retained_earnings / total_assets,
        "ebit_to_ta": ebit / total_assets,
    }

    if spec["uses_market_equity"]:
        if market_value_equity is None:
            raise ValueError(
                f"Variant '{variant_name}' requires market_value_equity; "
                "use z_prime if MVE is unavailable"
            )
        ratios["equity_to_liabilities"] = market_value_equity / book_value_total_liabilities
    else:
        ratios["equity_to_liabilities"] = book_value_equity / book_value_total_liabilities

    if spec["uses_sales"]:
        if sales is None:
            raise ValueError(f"Variant '{variant_name}' requires sales")
        ratios["sales_to_ta"] = sales / total_assets

    # Compute components and score
    components: dict[str, dict[str, float]] = {}
    score = spec["constant"]
    for ratio_name, weight in weights.items():
        value = ratios[ratio_name]
        contribution = weight * value
        components[ratio_name] = {
            "value": round(value, 6),
            "weight": weight,
            "contribution": round(contribution, 6),
        }
        score += contribution

    score = round(score, 4)
    thresholds = spec["thresholds"]
    classification = _classify(score, thresholds)

    return {
        "variant_used": variant_name,
        "components": components,
        "z_score": score,
        "classification": classification,
        "thresholds_used": thresholds,
    }


def execute(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    book_value_equity: float,
    book_value_total_liabilities: float,
    total_assets: float,
    variant: Literal["z", "z_prime", "z_double_prime", "em_z_double_prime", "all"],
    market_value_equity: float | None = None,
    sales: float | None = None,
) -> dict[str, Any]:
    """Compute Altman Z-score in the requested variant(s).

    Args:
        working_capital: Current assets minus current liabilities.
        retained_earnings: Accumulated retained earnings from BS.
        ebit: Earnings before interest and taxes.
        book_value_equity: Book value of equity (for Z', Z", EM Z").
        book_value_total_liabilities: Total liabilities book value.
        total_assets: Total assets.
        variant: Which variant(s) to compute.
            "z"               = public manufacturer (needs market_value_equity + sales)
            "z_prime"         = private manufacturer (needs sales)
            "z_double_prime"  = non-manufacturer (4 factors, no sales)
            "em_z_double_prime" = emerging markets (Z" + 3.25)
            "all"             = compute all four; returns list under "variants"
        market_value_equity: Market cap; required only for "z". None for others.
        sales: Net revenue; required for "z" and "z_prime". None for Z" variants.

    Returns:
        Dict with z_score, classification, thresholds_used, components per variant,
        or "variants" list when variant="all".

    Raises:
        ValueError: On missing required inputs or total_assets == 0.
    """
    if variant == "all":
        results = []
        for v in ["z", "z_prime", "z_double_prime", "em_z_double_prime"]:
            try:
                r = _compute_variant(
                    v,
                    working_capital,
                    retained_earnings,
                    ebit,
                    market_value_equity,
                    book_value_equity,
                    book_value_total_liabilities,
                    sales,
                    total_assets,
                )
                r["error"] = None
            except ValueError as exc:
                r = {"variant_used": v, "error": str(exc)}
            results.append(r)
        return {"variants": results}

    if variant not in _VARIANTS:
        raise ValueError(f"Unknown variant {variant!r}; valid: {list(_VARIANTS)}")

    return _compute_variant(
        variant,
        working_capital,
        retained_earnings,
        ebit,
        market_value_equity,
        book_value_equity,
        book_value_total_liabilities,
        sales,
        total_assets,
    )


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="altman_z_variants",
        category=Category.FORENSIC,
        one_liner='Altman Z-score in all four variants: Z, Z\', Z", EM Z".',
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute Altman bankruptcy-risk Z-score in the variant appropriate to the company "
            "(public manufacturer = Z, private = Z', non-manufacturer = Z\", "
            'emerging market = EM Z"). Produces score, classification (safe/gray/distress), '
            "and per-component contribution table."
        ),
        when_to_use=[
            "Credit context for any manufacturing, industrial, or general corporate name.",
            "Distress screening prior to a deep credit analysis.",
            "Cross-company distress mapping in a sector report.",
        ],
        when_not_to_use=[
            "Banks or insurers — use sector-specific credit panels (CET1, NCO, combined ratio).",
            "Pre-revenue development-stage companies — Z is not designed for negative-EBIT names.",
            "As a standalone verdict — pair with dividend_safety_panel or credit_solvency_panel.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "working_capital": HelperParam(
                type="float",
                required=True,
                description="Current assets minus current liabilities.",
            ),
            "retained_earnings": HelperParam(
                type="float",
                required=True,
                description="Accumulated retained earnings from balance sheet.",
            ),
            "ebit": HelperParam(
                type="float",
                required=True,
                description="Earnings before interest and taxes.",
            ),
            "book_value_equity": HelperParam(
                type="float",
                required=True,
                description='Book value of equity. Used by Z\', Z", EM Z".',
            ),
            "book_value_total_liabilities": HelperParam(
                type="float",
                required=True,
                description="Total liabilities at book value.",
            ),
            "total_assets": HelperParam(
                type="float",
                required=True,
                description="Total assets (denominator for most ratios).",
            ),
            "variant": HelperParam(
                type="Literal['z', 'z_prime', 'z_double_prime', 'em_z_double_prime', 'all']",
                required=True,
                description=(
                    "Which variant to compute. "
                    "'z' = public manufacturer (needs market_value_equity + sales). "
                    "'z_prime' = private manufacturer (needs sales). "
                    "'z_double_prime' = non-manufacturer (4 factors only). "
                    "'em_z_double_prime' = Z\" + 3.25 constant. "
                    "'all' = compute all four; errors per-variant where inputs missing."
                ),
            ),
            "market_value_equity": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Market capitalization. Required only for variant='z'.",
            ),
            "sales": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Net revenue. Required for variant='z' and 'z_prime'.",
            ),
        },
        outputs=[
            HelperOutput(
                name="altman_z_variants_output",
                type="altman_z_variants_output",
                description=(
                    "z_score, classification (safe/gray/distress), thresholds_used, "
                    "and components dict with value/weight/contribution per factor. "
                    "When variant='all', returns 'variants' list with one entry per model."
                ),
            ),
        ],
        produces_artifacts=["altman_z_variants_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
