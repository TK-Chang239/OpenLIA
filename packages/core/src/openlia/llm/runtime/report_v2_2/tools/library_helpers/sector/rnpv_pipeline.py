"""rnpv_pipeline — Pharma/biotech pipeline risk-adjusted NPV engine.

Registered name: "rnpv_pipeline"
Category: SECTOR_PHARMA

Computes per-asset rNPV across a pharmaceutical or biotech drug pipeline and
aggregates to total pipeline value.  Each asset is discounted by its stage-specific
probability of success (PoS), a revenue ramp from launch to peak, generic erosion
after patent expiry, and a royalty stack for outgoing royalty obligations.

Decision #5: PoS values are REQUIRED as user input — no built-in lookup table
shipped in-repo (Citeline license restriction).  See skill doc for published
industry norms to calibrate inputs.

Decision #16: royalty_stack_analyzer is an internal computation module of this
helper, not a standalone helper.

Design ref: planning/2026-05-22-helpers-design-sector-modules.md §4
"""

from __future__ import annotations

import datetime
from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Decision #5: empty PoS table — callers may patch for testing
# ---------------------------------------------------------------------------

DEFAULT_POS_TABLE: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Phase constants
# ---------------------------------------------------------------------------

_VALID_PHASES: frozenset[str] = frozenset(
    ["preclinical", "phase_1", "phase_2", "phase_3", "filed", "approved"]
)

# ---------------------------------------------------------------------------
# Revenue ramp profiles (multipliers by years-since-launch, index 0 = year 1)
# ---------------------------------------------------------------------------

_RAMP_PROFILES: dict[str, list[float]] = {
    "standard": [0.10, 0.40, 0.80, 1.00],  # 3-year ramp to peak
    "fast": [0.65, 1.00],  # 1-year ramp
    "slow": [0.05, 0.15, 0.35, 0.65, 0.90, 1.00],  # 5-year ramp
}

# Post-LOE generic erosion curve (index 0 = year of LOE, index 1 = year+1, etc.)
# Applied as a fraction of pre-LOE revenue at that year.
_LOE_DECAY_CURVE: list[float] = [1.0, 0.35, 0.20, 0.15, 0.10]
_LOE_DECAY_FLOOR = 0.10  # beyond index 4

# ---------------------------------------------------------------------------
# Internal: royalty_stack_analyzer
# Decision #16: internal module, not standalone
# ---------------------------------------------------------------------------


def _royalty_stack_burden(
    royalty_rate: float,
    annual_revenues: list[float],
    discount_rate: float,
    current_year: int,
    launch_year: int,
) -> float:
    """Compute PV of total royalty burden owed to licensors.

    Royalty burden per year = revenue * royalty_rate.
    PV-discounted from each revenue year back to current_year.

    Returns the total present value of royalties paid out.
    """
    if royalty_rate <= 0.0:
        return 0.0
    total_pv = 0.0
    for i, rev in enumerate(annual_revenues):
        year = launch_year + i
        t = year - current_year
        royalty_payment = rev * royalty_rate
        if t <= 0:
            # Year is in the past or current year — no discounting
            total_pv += royalty_payment
        else:
            total_pv += royalty_payment / ((1 + discount_rate) ** t)
    return total_pv


# ---------------------------------------------------------------------------
# Internal: revenue stream builder per asset
# ---------------------------------------------------------------------------


def _build_revenue_stream(
    peak_sales_estimate: float,
    launch_year: int,
    patent_expiry: int,
    royalty_rate: float,
    ramp_curve: str,
    terminal_year: int,
) -> list[tuple[int, float]]:
    """Build year-by-year gross revenue stream from launch to terminal year.

    Returns list of (year, gross_revenue_to_company_after_royalties).
    Patent cliff applied post-patent_expiry using _LOE_DECAY_CURVE.
    """
    profile = _RAMP_PROFILES.get(ramp_curve, _RAMP_PROFILES["standard"])
    results: list[tuple[int, float]] = []
    net_multiplier = 1.0 - royalty_rate  # royalties reduce company net revenue

    for year in range(launch_year, terminal_year + 1):
        years_since_launch = year - launch_year
        years_past_loe = year - patent_expiry

        if years_past_loe > 0:
            # Post-LOE: apply generic erosion curve
            decay_idx = min(years_past_loe - 1, len(_LOE_DECAY_CURVE) - 1)
            if years_past_loe - 1 >= len(_LOE_DECAY_CURVE):
                erosion = _LOE_DECAY_FLOOR
            else:
                erosion = _LOE_DECAY_CURVE[decay_idx]
            gross_rev = peak_sales_estimate * erosion
        else:
            # Pre-LOE: apply ramp curve
            ramp_idx = min(years_since_launch, len(profile) - 1)
            gross_rev = peak_sales_estimate * profile[ramp_idx]

        net_rev = gross_rev * net_multiplier
        results.append((year, net_rev))

    return results


# ---------------------------------------------------------------------------
# Internal: per-asset rNPV computation
# ---------------------------------------------------------------------------


def _compute_asset_rnpv(
    *,
    name: str,
    phase: str,
    indication: str,
    peak_sales_estimate: float,
    launch_year: int,
    patent_expiry: int,
    royalty_rate: float,
    pos: float,
    cogs_pct: float,
    sga_pct: float,
    tax_rate: float,
    discount_rate: float,
    ramp_curve: str,
    terminal_year: int,
    current_year: int,
) -> dict[str, Any]:
    """Compute per-asset rNPV components.

    Steps:
    1. Build net revenue stream (post-royalties) from launch to terminal_year.
    2. Apply operating cost structure (COGS + SGA) to derive EBIT.
    3. Tax-effect to NOPAT.
    4. PV-discount each year's NOPAT back to current_year.
    5. Risk-adjust by multiplying sum by pos.
    6. Royalty burden computed separately (already netted in revenue; reported gross).

    Returns dict with per-asset rNPV fields per spec output schema.
    """
    # Validate phase
    if phase not in _VALID_PHASES:
        raise ValueError(
            f"Asset '{name}': phase '{phase}' not in valid set {sorted(_VALID_PHASES)}. "
            f"Check phase spelling."
        )

    # Build revenue stream
    revenue_stream = _build_revenue_stream(
        peak_sales_estimate=peak_sales_estimate,
        launch_year=launch_year,
        patent_expiry=patent_expiry,
        royalty_rate=royalty_rate,
        ramp_curve=ramp_curve,
        terminal_year=terminal_year,
    )

    # Compute undiscounted operating cash flows and PV sum (unrisked)
    op_margin = 1.0 - cogs_pct - sga_pct  # gross operating margin after COGS + SGA
    unrisked_npv_sum = 0.0
    for year, net_rev in revenue_stream:
        ebit = net_rev * op_margin
        nopat = ebit * (1.0 - tax_rate)
        t = year - current_year
        if t <= 0:
            pv = nopat
        else:
            pv = nopat / ((1.0 + discount_rate) ** t)
        unrisked_npv_sum += pv

    # Risk-adjusted NPV
    risked_npv = unrisked_npv_sum * pos

    # Royalty burden: PV of royalties owed (separately, for disclosure)
    # Royalties are already netted from revenues above, so this is just for reporting
    gross_revenues = [
        rev / (1.0 - royalty_rate) if royalty_rate < 1.0 else 0.0 for _, rev in revenue_stream
    ]
    royalty_burden = _royalty_stack_burden(
        royalty_rate=royalty_rate,
        annual_revenues=gross_revenues,
        discount_rate=discount_rate,
        current_year=current_year,
        launch_year=launch_year,
    )

    net_npv = risked_npv  # royalties already netted in revenue stream

    # Patent cliff impact: PV loss due to LOE (unrisked)
    # Compute "no-cliff" scenario and measure the difference
    peak_revenue_annual = peak_sales_estimate * (1.0 - royalty_rate)
    no_cliff_pv = 0.0
    for year, _ in revenue_stream:
        years_since_launch = year - launch_year
        ramp_profile = _RAMP_PROFILES.get(ramp_curve, _RAMP_PROFILES["standard"])
        ramp_idx = min(years_since_launch, len(ramp_profile) - 1)
        no_cliff_rev = peak_revenue_annual * ramp_profile[ramp_idx]
        no_cliff_ebit = no_cliff_rev * op_margin
        no_cliff_nopat = no_cliff_ebit * (1.0 - tax_rate)
        t = year - current_year
        if t <= 0:
            pv = no_cliff_nopat
        else:
            pv = no_cliff_nopat / ((1.0 + discount_rate) ** t)
        no_cliff_pv += pv

    patent_cliff_impact = unrisked_npv_sum - no_cliff_pv  # negative = LOE destroys value

    # Peak sales year: last year ramp profile hits 1.0
    ramp_profile = _RAMP_PROFILES.get(ramp_curve, _RAMP_PROFILES["standard"])
    peak_sales_year = launch_year + len(ramp_profile) - 1

    return {
        "name": name,
        "phase": phase,
        "indication": indication,
        "pos": pos,
        "unrisked_npv": round(unrisked_npv_sum, 2),
        "risked_npv": round(risked_npv, 2),
        "royalty_burden": round(royalty_burden, 2),
        "net_npv": round(net_npv, 2),
        "peak_sales_year": peak_sales_year,
        "patent_cliff_impact": round(patent_cliff_impact, 2),
    }


# ---------------------------------------------------------------------------
# Main execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    ticker: str,
    assets: list[dict[str, Any]],
    discount_rate: float,
    cogs_pct: float = 0.15,
    sga_pct: float = 0.30,
    tax_rate: float = 0.21,
    ramp_curve: str = "standard",
    terminal_year: int = 2045,
    platform_value: float = 0.0,
    pos_overrides: dict[str, float] | None = None,
    data_as_of: str | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute rNPV across a pharma/biotech pipeline.

    Args:
        ticker: Company ticker, e.g. "VRTX".
        assets: List of pipeline asset dicts. Each must include:
            name (str), phase (str), indication (str),
            peak_sales_estimate (float, $M), launch_year (int),
            patent_expiry (int), pos (float, required per decision #5).
            Optional: royalty_rate (float, default 0.0),
                      cogs_pct (float, overrides global),
                      sga_pct (float, overrides global),
                      tax_rate (float, overrides global),
                      ramp_curve (str, overrides global).
        discount_rate: Risk-adjusted cost of capital as decimal (e.g. 0.10 for 10%).
            Typically 9-12% for biotech; lower for diversified pharma.
        cogs_pct: Cost of goods as % of net revenue. Default 15%.
        sga_pct: SG&A as % of net revenue. Default 30%.
        tax_rate: Effective tax rate. Default 21%.
        ramp_curve: Revenue ramp profile: "standard" (3-year), "fast" (1-year),
            "slow" (5-year). Default "standard".
        terminal_year: Last year of explicit cash flows. Default 2045.
        platform_value: NPV of technology platform separate from pipeline ($M). Default 0.
        pos_overrides: Asset-name-keyed PoS override dict. Merged into asset pos values.
        data_as_of: ISO date for data freshness.

    Returns:
        Dict with assets (per-asset rNPV), total_pipeline_value, value_concentration,
        platform_value, warnings, pos_overrides_used.

    Raises:
        ValueError: If any asset is missing required 'pos' field.
        ValueError: If any asset has an invalid 'phase' value.
        ValueError: If discount_rate <= 0.
    """
    if discount_rate <= 0:
        raise ValueError(
            f"discount_rate must be positive; got {discount_rate}. "
            f"Typical pharma discount rates are 9-12%."
        )

    current_year = datetime.date.today().year
    warnings: list[str] = []
    pos_overrides_used: list[str] = []
    overrides = pos_overrides or {}

    computed_assets: list[dict[str, Any]] = []

    for asset in assets:
        name: str = asset.get("name", "unnamed")
        phase: str = asset.get("phase", "")
        indication: str = asset.get("indication", "")
        peak_sales_estimate: float | None = asset.get("peak_sales_estimate")
        launch_year: int | None = asset.get("launch_year")
        patent_expiry: int | None = asset.get("patent_expiry")
        royalty_rate: float = float(asset.get("royalty_rate", 0.0))

        # PoS: required — user must supply per decision #5
        pos_raw = asset.get("pos")
        if name in overrides:
            pos_raw = overrides[name]
            pos_overrides_used.append(name)

        if pos_raw is None:
            raise ValueError(
                f"Asset '{name}' missing required 'pos' value. "
                f"Probability-of-success values must be user-supplied per execution-strategy "
                f"decision #5. Recommend looking up phase-specific PoS from Citeline 2024 "
                f"pipeline analytics or a comparable industry source."
            )
        pos = float(pos_raw)
        if not (0.0 <= pos <= 1.0):
            raise ValueError(
                f"Asset '{name}': pos={pos} outside [0, 1]. "
                f"PoS must be a probability between 0 and 1."
            )

        # Validate required numeric fields
        if peak_sales_estimate is None:
            raise ValueError(f"Asset '{name}' missing required 'peak_sales_estimate'.")
        if launch_year is None:
            raise ValueError(f"Asset '{name}' missing required 'launch_year'.")
        if patent_expiry is None:
            raise ValueError(f"Asset '{name}' missing required 'patent_expiry'.")

        # Per-asset overrides for cost structure
        asset_cogs = float(asset.get("cogs_pct", cogs_pct))
        asset_sga = float(asset.get("sga_pct", sga_pct))
        asset_tax = float(asset.get("tax_rate", tax_rate))
        asset_ramp = str(asset.get("ramp_curve", ramp_curve))

        if patent_expiry <= launch_year:
            warnings.append(
                f"Asset '{name}': patent_expiry ({patent_expiry}) <= launch_year ({launch_year}). "
                f"Generic erosion starts immediately at launch."
            )

        result = _compute_asset_rnpv(
            name=name,
            phase=phase,
            indication=indication,
            peak_sales_estimate=float(peak_sales_estimate),
            launch_year=int(launch_year),
            patent_expiry=int(patent_expiry),
            royalty_rate=royalty_rate,
            pos=pos,
            cogs_pct=asset_cogs,
            sga_pct=asset_sga,
            tax_rate=asset_tax,
            discount_rate=discount_rate,
            ramp_curve=asset_ramp,
            terminal_year=terminal_year,
            current_year=current_year,
        )
        computed_assets.append(result)

    # Pipeline aggregate
    total_pipeline_value = round(sum(a["net_npv"] for a in computed_assets), 2)
    total_pipeline_abs = sum(abs(a["net_npv"]) for a in computed_assets)

    # Value concentration (top-3 assets by absolute rNPV contribution)
    sorted_assets = sorted(computed_assets, key=lambda a: abs(a["net_npv"]), reverse=True)
    top_3_names: list[str] = [a["name"] for a in sorted_assets[:3]]
    top_1_pct: float | None = None
    top_3_pct: float | None = None
    if total_pipeline_abs > 0:
        top_1_pct = round(abs(sorted_assets[0]["net_npv"]) / total_pipeline_abs, 4)
        top_3_abs = sum(abs(a["net_npv"]) for a in sorted_assets[:3])
        top_3_pct = round(top_3_abs / total_pipeline_abs, 4)

    value_concentration: dict[str, Any] = {
        "top_1_asset": top_3_names[0] if top_3_names else None,
        "top_3_assets": top_3_names,
        "top_1_pct_of_pipeline": top_1_pct,
        "top_3_pct_of_pipeline": top_3_pct,
    }

    if top_1_pct is not None and top_1_pct > 0.50:
        warnings.append(
            f"High binary event risk: {top_3_names[0]!r} represents "
            f"{top_1_pct:.0%} of total pipeline value — single-asset concentration."
        )

    # Preclinical assets with negative rNPV are informative but exclude from warnings
    neg_rnpv_assets = [a["name"] for a in computed_assets if a["net_npv"] < 0]
    if neg_rnpv_assets:
        warnings.append(
            f"Negative rNPV assets (stage PoS does not cover remaining R&D burden): "
            f"{', '.join(neg_rnpv_assets)}. Normal for early-stage assets — value is in the option."
        )

    # Narrative
    asset_count = len(computed_assets)
    parts: list[str] = [f"{ticker}: {asset_count} pipeline asset(s)"]
    parts.append(f"total pipeline rNPV ${total_pipeline_value:,.1f}M")
    if platform_value > 0:
        parts.append(f"platform value ${platform_value:,.1f}M")
    narrative = "; ".join(parts) + "."
    if top_1_pct is not None and top_1_pct > 0.50 and top_3_names:
        narrative += f" Binary risk: {top_1_pct:.0%} of pipeline value in {top_3_names[0]!r}."

    return {
        "ticker": ticker,
        "assets": computed_assets,
        "total_pipeline_value": total_pipeline_value,
        "value_concentration": value_concentration,
        "platform_value": round(platform_value, 2),
        "warnings": warnings,
        "pos_overrides_used": pos_overrides_used,
        "narrative": narrative,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="rnpv_pipeline",
        category=Category.SECTOR_PHARMA,
        one_liner=(
            "Pharma/biotech pipeline rNPV engine: per-asset risk-adjusted NPV "
            "with royalty stack, patent cliff modeling, and value concentration."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute risk-adjusted net present value (rNPV) of a pharmaceutical or biotech "
            "pipeline, asset by asset.  Each clinical-stage asset is discounted by its "
            "probability of success (PoS), a revenue ramp from launch to peak, generic "
            "erosion after patent expiry, and outgoing royalty obligations.  Aggregates "
            "to total pipeline value and flags binary event concentration risk.  "
            "Mandatory for any pharma/biotech company where pipeline assets represent "
            ">25% of estimated total value."
        ),
        when_to_use=[
            "Initiating coverage on any pharma or biotech with meaningful clinical-stage pipeline.",
            "Post-trial readout updates — reprice one asset's PoS and rerun.",
            "Sector report benchmarking pipeline value across companies in the same "
            "therapeutic area.",
            "Single-asset biotech where rNPV IS the entire equity value.",
        ],
        when_not_to_use=[
            "Royalty-pharma companies (Royalty Pharma, RPRX) — use stream_dcf instead; "
            "these hold royalty streams on approved drugs, not development-stage assets.",
            "Pure commercial pharma with no pipeline (only marketed drugs) — use dcf_engine.",
            "Medical devices — rNPV framework applies but regulatory pathway differs; "
            "PoS norms from Citeline (pharma) do not apply to 510(k) or PMA pathways.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                description="Company ticker, e.g. 'VRTX'.",
                required=True,
            ),
            "assets": HelperParam(
                type="list[dict]",
                description=(
                    "Pipeline asset dicts. Each requires: name (str), phase (str), "
                    "indication (str), peak_sales_estimate (float, $M), launch_year (int), "
                    "patent_expiry (int), pos (float, required per decision #5). "
                    "Optional per-asset overrides: royalty_rate, cogs_pct, sga_pct, "
                    "tax_rate, ramp_curve."
                ),
                required=True,
            ),
            "discount_rate": HelperParam(
                type="float",
                description=(
                    "Risk-adjusted cost of capital as decimal. Typically 0.09-0.12 for "
                    "development-stage biotech; lower (0.07-0.09) for diversified pharma."
                ),
                required=True,
            ),
            "cogs_pct": HelperParam(
                type="float",
                default=0.15,
                description="Cost of goods as % of net revenue. Default 15%.",
                required=False,
            ),
            "sga_pct": HelperParam(
                type="float",
                default=0.30,
                description="SG&A as % of net revenue. Default 30%.",
                required=False,
            ),
            "tax_rate": HelperParam(
                type="float",
                default=0.21,
                description="Effective tax rate. Default 21%.",
                required=False,
            ),
            "ramp_curve": HelperParam(
                type="str",
                default="standard",
                description=(
                    "Revenue ramp profile: 'standard' (3-year), 'fast' (1-year), "
                    "'slow' (5-year). Default 'standard'."
                ),
                required=False,
            ),
            "terminal_year": HelperParam(
                type="int",
                default=2045,
                description="Last year of explicit cash flows. Default 2045.",
                required=False,
            ),
            "platform_value": HelperParam(
                type="float",
                default=0.0,
                description=(
                    "NPV of technology platform separate from individual pipeline assets ($M). "
                    "For platform biotechs (e.g., mRNA platforms). Default 0."
                ),
                required=False,
            ),
            "pos_overrides": HelperParam(
                type="dict",
                default=None,
                description=(
                    "Asset-name-keyed PoS override dict, e.g. {'Drug_X': 0.45}. "
                    "Overrides the pos field in the asset dict when provided."
                ),
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="rnpv_pipeline_output",
                type="rnpv_pipeline_output",
                description=(
                    "Per-asset rNPV breakdown (unrisked NPV, risked NPV, royalty burden, "
                    "net NPV, patent cliff impact), total pipeline value, value concentration "
                    "(top-3 asset share), platform value, warnings (binary risk, negative rNPV), "
                    "and narrative."
                ),
            ),
        ],
        produces_artifacts=["rnpv_pipeline_output"],
        consumes_artifacts=[],
        data_dependencies=[],
    ),
    skill_doc=SkillDocRef(
        path="skills/rnpv_pipeline.md",
        estimated_tokens=2000,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
