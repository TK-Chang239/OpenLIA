"""reit_valuation_panel — REIT-specific KPI and valuation panel.

Registered name: "reit_valuation_panel"
Category: SECTOR_REITS

Computes and synthesizes four canonical REIT metric blocks:

  Income:      FFO, AFFO, AFFO payout ratio, FFO/AFFO growth.
  Valuation:   P/FFO, P/AFFO, NAV per share, implied cap rate,
               premium/discount to NAV.
  Operating:   Same-store NOI growth, occupancy, WALT, re-leasing spreads,
               lease expiration ladder, tenant concentration.
  Balance sheet: Net Debt/EBITDA, debt-to-assets, unsecured debt mix,
               interest coverage, weighted average debt maturity.

GAAP earnings and P/E are meaningless for REITs — depreciation is not an
economic cost for real estate; book value understates fair value.
FFO/AFFO and NAV are the institutional anchors.

NAV requires user-supplied cap rate assumptions per decision #15.
CBRE cap-rate surveys require a subscription and cannot be hard-coded.

Design ref: planning/2026-05-22-helpers-design-sector-modules.md §3
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
# AFFO sustainability score helpers
# ---------------------------------------------------------------------------


def _affo_sustainability_score(
    affo_payout_ratio: float | None,
    ss_noi_growth: float | None,
    occupancy: float | None,
    net_debt_ebitda: float | None,
) -> float | None:
    """Weighted AFFO sustainability score [0, 100].

    Component weights:
    - AFFO payout ratio (inverted):  35%
    - Same-store NOI growth:         25%
    - Occupancy rate:                20%
    - Net Debt/EBITDA (inverted):    20%
    """
    components: list[tuple[float, float]] = []

    if affo_payout_ratio is not None:
        # < 0.65 -> 1.0, 0.65-0.80 -> 0.75, 0.80-0.95 -> 0.40, > 0.95 -> 0.10
        if affo_payout_ratio < 0.65:
            s = 1.0
        elif affo_payout_ratio < 0.80:
            s = 0.75
        elif affo_payout_ratio < 0.95:
            s = 0.40
        else:
            s = 0.10
        components.append((s, 0.35))

    if ss_noi_growth is not None:
        # > 5% -> 1.0, 3-5% -> 0.80, 1-3% -> 0.55, 0-1% -> 0.30, < 0 -> 0.0
        if ss_noi_growth >= 0.05:
            s = 1.0
        elif ss_noi_growth >= 0.03:
            s = 0.80
        elif ss_noi_growth >= 0.01:
            s = 0.55
        elif ss_noi_growth >= 0.00:
            s = 0.30
        else:
            s = 0.0
        components.append((s, 0.25))

    if occupancy is not None:
        # >= 97% -> 1.0, 94-97% -> 0.75, 90-94% -> 0.45, < 90% -> 0.15
        if occupancy >= 0.97:
            s = 1.0
        elif occupancy >= 0.94:
            s = 0.75
        elif occupancy >= 0.90:
            s = 0.45
        else:
            s = 0.15
        components.append((s, 0.20))

    if net_debt_ebitda is not None:
        # < 4x -> 1.0, 4-6x -> 0.70, 6-8x -> 0.35, > 8x -> 0.05
        if net_debt_ebitda < 4.0:
            s = 1.0
        elif net_debt_ebitda < 6.0:
            s = 0.70
        elif net_debt_ebitda < 8.0:
            s = 0.35
        else:
            s = 0.05
        components.append((s, 0.20))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    raw = sum(s * w for s, w in components) / total_weight
    return round(raw * 100, 1)


def _composite_reit_health(
    affo_sustainability: float | None,
    nav_discount_pct: float | None,
    interest_coverage: float | None,
) -> float | None:
    """Composite REIT health score [0, 100].

    Weights:
    - AFFO sustainability (already composite):  50%
    - NAV premium/discount context:             25%
    - Interest coverage:                        25%
    """
    components: list[tuple[float, float]] = []

    if affo_sustainability is not None:
        components.append((affo_sustainability / 100.0, 0.50))

    if nav_discount_pct is not None:
        # Discount to NAV > -20% -> 1.0, -20% to -10% -> 0.70, -10% to 0% -> 0.85,
        # 0% to 20% -> 0.70, > 20% premium -> 0.40
        d = nav_discount_pct
        if d <= -0.20:
            s = 1.0  # deep discount — good for new buyers
        elif d <= -0.10:
            s = 0.85
        elif d <= 0.0:
            s = 0.75
        elif d <= 0.20:
            s = 0.60
        else:
            s = 0.40
        components.append((s, 0.25))

    if interest_coverage is not None:
        # > 4x -> 1.0, 3-4x -> 0.75, 2-3x -> 0.45, < 2x -> 0.10
        if interest_coverage > 4.0:
            s = 1.0
        elif interest_coverage >= 3.0:
            s = 0.75
        elif interest_coverage >= 2.0:
            s = 0.45
        else:
            s = 0.10
        components.append((s, 0.25))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    raw = sum(s * w for s, w in components) / total_weight
    return round(raw * 100, 1)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    ticker: str,
    financials: dict[str, Any],
    cap_rate_assumptions: dict[str, Any],
    comparison_period: str | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute the REIT valuation and KPI panel.

    Args:
        ticker: Company ticker, e.g. "O", "PLD", "EXR".
        financials: REIT-specific line items dict. Recognised keys (all optional
            unless noted):
            net_income (required for FFO),
            real_estate_depreciation (required for FFO),
            gains_on_sales (subtracted in FFO),
            losses_on_sales (added in FFO),
            impairment_charges (added in FFO),
            recurring_capex (required for AFFO),
            straight_line_rent_adj (subtracted in AFFO),
            stock_based_comp (added in AFFO),
            nareit_ffo_disclosed (disclosed NAREIT FFO for reconciliation),
            dividends_paid (TTM; for AFFO payout ratio),
            ffo_prior_period (for QoQ growth),
            ffo_prior_year (for YoY growth),
            shares_outstanding (diluted),
            market_cap (current),
            total_debt,
            preferred_equity (default 0),
            cash_and_equivalents,
            total_assets,
            unsecured_debt,
            ebitda,
            interest_expense,
            weighted_avg_debt_maturity (years),
            noi_annualized (for implied cap rate and NAV),
            same_store_noi_current,
            same_store_noi_prior_year,
            occupancy_rate (decimal, e.g. 0.95),
            walt_years (weighted average lease term),
            releasing_spread_pct (new vs expiring rent),
            tenant_concentration_top10_pct,
            lease_expiry_ladder (dict: {"2025": 0.08, "2026": 0.12, ...}),
            current_price (per share).
        cap_rate_assumptions: Required. User-supplied cap rates per property type.
            Must contain at least one key. Example:
            {"blended": 0.055} or {"industrial": 0.045, "office": 0.065}.
            The helper uses "blended" if present, otherwise takes the
            first provided cap rate value.
        comparison_period: Comparison period label. Informational only.
        data_as_of: ISO date for data freshness.
        source_provenance: Upstream citation IDs.

    Returns:
        Structured dict with income, valuation, operating_metrics,
        balance_sheet blocks; plus AFFO sustainability score,
        composite REIT health score (0-100), warnings, and narrative.

    Raises:
        ValueError: When cap_rate_assumptions is missing or empty.
    """
    if not cap_rate_assumptions:
        raise ValueError(
            "REIT NAV requires user-supplied cap rate assumptions per decision #15. "
            "Provide cap_rate_assumptions={'blended': 0.055} or per-property-type "
            "cap rates. CBRE/JLL surveys require a subscription and cannot be "
            "hard-coded into this helper."
        )

    warnings: list[str] = []
    f = financials

    # ------------------------------------------------------------------
    # Resolve cap rate
    # ------------------------------------------------------------------
    if "blended" in cap_rate_assumptions:
        applied_cap_rate: float = float(cap_rate_assumptions["blended"])
    else:
        applied_cap_rate = float(next(iter(cap_rate_assumptions.values())))

    # ------------------------------------------------------------------
    # 1. FFO (NAREIT definition)
    # FFO = NI + D&A + losses_on_sales - gains_on_sales + impairment
    # ------------------------------------------------------------------
    net_income: float | None = f.get("net_income")
    re_depreciation: float | None = f.get("real_estate_depreciation")
    gains_on_sales: float | None = f.get("gains_on_sales", 0.0)
    losses_on_sales: float | None = f.get("losses_on_sales", 0.0)
    impairment: float | None = f.get("impairment_charges", 0.0)

    ffo: float | None = None
    if net_income is not None and re_depreciation is not None:
        gains_on_sales = gains_on_sales or 0.0
        losses_on_sales = losses_on_sales or 0.0
        impairment = impairment or 0.0
        ffo = net_income + re_depreciation + losses_on_sales - gains_on_sales + impairment

    shares: float | None = f.get("shares_outstanding")
    ffo_per_share: float | None = None
    if ffo is not None and shares is not None and shares > 0:
        ffo_per_share = ffo / shares

    nareit_ffo_disclosed: float | None = f.get("nareit_ffo_disclosed")
    ffo_matches_disclosed: bool | None = None
    if ffo is not None and nareit_ffo_disclosed is not None and nareit_ffo_disclosed != 0:
        diff_pct = abs(ffo - nareit_ffo_disclosed) / abs(nareit_ffo_disclosed)
        ffo_matches_disclosed = diff_pct <= 0.02
        if not ffo_matches_disclosed:
            warnings.append(
                f"Computed FFO {ffo:,.0f} differs from disclosed NAREIT FFO "
                f"{nareit_ffo_disclosed:,.0f} by {diff_pct:.1%} (>2% tolerance)."
            )

    # FFO QoQ and YoY growth
    ffo_prior_period: float | None = f.get("ffo_prior_period")
    ffo_prior_year: float | None = f.get("ffo_prior_year")
    ffo_growth_qoq: float | None = None
    ffo_growth_yoy: float | None = None
    if ffo is not None and ffo_prior_period is not None and ffo_prior_period != 0:
        ffo_growth_qoq = (ffo - ffo_prior_period) / abs(ffo_prior_period)
    if ffo is not None and ffo_prior_year is not None and ffo_prior_year != 0:
        ffo_growth_yoy = (ffo - ffo_prior_year) / abs(ffo_prior_year)

    income_block = {
        "net_income": net_income,
        "real_estate_depreciation_added": re_depreciation,
        "gains_on_sales_subtracted": gains_on_sales,
        "losses_on_sales_added": losses_on_sales,
        "impairment_charges_added": impairment,
        "ffo": ffo,
        "ffo_per_share_diluted": round(ffo_per_share, 4) if ffo_per_share is not None else None,
        "nareit_ffo_disclosed": nareit_ffo_disclosed,
        "ffo_matches_disclosed": ffo_matches_disclosed,
        "ffo_growth_qoq_pct": round(ffo_growth_qoq, 6) if ffo_growth_qoq is not None else None,
        "ffo_growth_yoy_pct": round(ffo_growth_yoy, 6) if ffo_growth_yoy is not None else None,
    }

    # ------------------------------------------------------------------
    # 2. AFFO
    # AFFO = FFO - recurring_capex - straight_line_rent_adj + sbc
    # ------------------------------------------------------------------
    recurring_capex: float | None = f.get("recurring_capex")
    sl_rent_adj: float | None = f.get("straight_line_rent_adj", 0.0)
    sbc: float | None = f.get("stock_based_comp", 0.0)

    affo: float | None = None
    if ffo is not None and recurring_capex is not None:
        sl_rent_adj = sl_rent_adj or 0.0
        sbc = sbc or 0.0
        affo = ffo - recurring_capex - sl_rent_adj + sbc

    affo_per_share: float | None = None
    if affo is not None and shares is not None and shares > 0:
        affo_per_share = affo / shares

    dividends_paid: float | None = f.get("dividends_paid")
    affo_payout_ratio: float | None = None
    if dividends_paid is not None and affo is not None and affo > 0:
        affo_payout_ratio = dividends_paid / affo

    if affo_payout_ratio is not None and affo_payout_ratio > 0.80:
        warnings.append(
            f"AFFO payout ratio {affo_payout_ratio:.1%} exceeds 80% safety threshold. "
            f"Dividend growth is constrained; evaluate sustainability."
        )

    # AFFO QoQ and YoY growth (derived from FFO growth proxy when available)
    affo_prior_period: float | None = f.get("affo_prior_period")
    affo_prior_year: float | None = f.get("affo_prior_year")
    affo_growth_qoq: float | None = None
    affo_growth_yoy: float | None = None
    if affo is not None and affo_prior_period is not None and affo_prior_period != 0:
        affo_growth_qoq = (affo - affo_prior_period) / abs(affo_prior_period)
    if affo is not None and affo_prior_year is not None and affo_prior_year != 0:
        affo_growth_yoy = (affo - affo_prior_year) / abs(affo_prior_year)

    affo_block = {
        "ffo": ffo,
        "recurring_capex_subtracted": recurring_capex,
        "straight_line_rent_adj_subtracted": sl_rent_adj,
        "stock_based_comp_added": sbc,
        "affo": affo,
        "affo_per_share_diluted": round(affo_per_share, 4) if affo_per_share is not None else None,
        "affo_payout_ratio": round(affo_payout_ratio, 6) if affo_payout_ratio is not None else None,
        "affo_growth_qoq_pct": round(affo_growth_qoq, 6) if affo_growth_qoq is not None else None,
        "affo_growth_yoy_pct": round(affo_growth_yoy, 6) if affo_growth_yoy is not None else None,
    }

    # ------------------------------------------------------------------
    # 3. Valuation multiples and NAV
    # ------------------------------------------------------------------
    market_cap: float | None = f.get("market_cap")
    current_price: float | None = f.get("current_price")
    total_debt: float | None = f.get("total_debt")
    preferred_equity: float | None = f.get("preferred_equity", 0.0) or 0.0
    cash: float | None = f.get("cash_and_equivalents")
    noi_annualized: float | None = f.get("noi_annualized")

    # P/FFO and P/AFFO
    p_ffo: float | None = None
    if market_cap is not None and ffo is not None and ffo > 0:
        p_ffo = market_cap / ffo
    elif ffo_per_share is not None and current_price is not None and ffo_per_share > 0:
        p_ffo = current_price / ffo_per_share

    p_affo: float | None = None
    if market_cap is not None and affo is not None and affo > 0:
        p_affo = market_cap / affo
    elif affo_per_share is not None and current_price is not None and affo_per_share > 0:
        p_affo = current_price / affo_per_share

    # Implied cap rate = NOI / EV  (EV = market_cap + debt + preferred - cash)
    ev: float | None = None
    implied_cap_rate: float | None = None
    if market_cap is not None and total_debt is not None and cash is not None:
        ev = market_cap + total_debt + preferred_equity - cash
        if ev > 0 and noi_annualized is not None:
            implied_cap_rate = noi_annualized / ev

    # NAV calculation: implied_re_value = NOI / applied_cap_rate
    # NAV equity = implied_re_value + cash - debt - preferred
    # NAV per share = NAV equity / shares
    nav_per_share: float | None = None
    nav_equity: float | None = None
    implied_re_value: float | None = None
    premium_discount_to_nav: float | None = None

    if noi_annualized is not None and applied_cap_rate > 0:
        implied_re_value = noi_annualized / applied_cap_rate
        if total_debt is not None and cash is not None:
            nav_equity = implied_re_value + cash - total_debt - preferred_equity
            if shares is not None and shares > 0:
                nav_per_share = nav_equity / shares
                if current_price is not None and nav_per_share > 0:
                    premium_discount_to_nav = current_price / nav_per_share - 1

    valuation_block = {
        "p_ffo": round(p_ffo, 4) if p_ffo is not None else None,
        "p_affo": round(p_affo, 4) if p_affo is not None else None,
        "applied_cap_rate_pct": applied_cap_rate,
        "cap_rate_source": "user_supplied",
        "implied_cap_rate_pct": round(implied_cap_rate, 6)
        if implied_cap_rate is not None
        else None,
        "enterprise_value": round(ev, 2) if ev is not None else None,
        "implied_real_estate_value": round(implied_re_value, 2)
        if implied_re_value is not None
        else None,
        "cash_and_equivalents": cash,
        "total_debt": total_debt,
        "preferred_equity": preferred_equity,
        "nav_equity": round(nav_equity, 2) if nav_equity is not None else None,
        "nav_per_share": round(nav_per_share, 4) if nav_per_share is not None else None,
        "current_price": current_price,
        "premium_discount_to_nav_pct": round(premium_discount_to_nav, 6)
        if premium_discount_to_nav is not None
        else None,
    }

    # ------------------------------------------------------------------
    # 4. Operating metrics
    # ------------------------------------------------------------------
    ss_noi_current: float | None = f.get("same_store_noi_current")
    ss_noi_prior: float | None = f.get("same_store_noi_prior_year")
    ss_noi_growth: float | None = None
    if ss_noi_current is not None and ss_noi_prior is not None and ss_noi_prior != 0:
        ss_noi_growth = (ss_noi_current - ss_noi_prior) / abs(ss_noi_prior)

    occupancy: float | None = f.get("occupancy_rate")
    walt: float | None = f.get("walt_years")
    releasing_spread: float | None = f.get("releasing_spread_pct")
    tenant_concentration: float | None = f.get("tenant_concentration_top10_pct")
    lease_expiry_ladder: dict | None = f.get("lease_expiry_ladder")

    operating_block = {
        "same_store_noi_current": ss_noi_current,
        "same_store_noi_prior_year": ss_noi_prior,
        "same_store_noi_growth_pct": round(ss_noi_growth, 6) if ss_noi_growth is not None else None,
        "occupancy_rate_pct": occupancy,
        "walt_years": walt,
        "releasing_spread_pct": releasing_spread,
        "tenant_concentration_top10_pct": tenant_concentration,
        "lease_expiry_ladder": lease_expiry_ladder,
    }

    # ------------------------------------------------------------------
    # 5. Balance sheet / leverage
    # ------------------------------------------------------------------
    total_assets: float | None = f.get("total_assets")
    unsecured_debt: float | None = f.get("unsecured_debt")
    ebitda: float | None = f.get("ebitda")
    interest_expense: float | None = f.get("interest_expense")
    wam_debt: float | None = f.get("weighted_avg_debt_maturity")

    net_debt: float | None = None
    if total_debt is not None and cash is not None:
        net_debt = total_debt - cash

    net_debt_ebitda: float | None = None
    if net_debt is not None and ebitda is not None and ebitda > 0:
        net_debt_ebitda = net_debt / ebitda

    debt_to_assets: float | None = None
    if total_debt is not None and total_assets is not None and total_assets > 0:
        debt_to_assets = total_debt / total_assets

    unsecured_pct: float | None = None
    if unsecured_debt is not None and total_debt is not None and total_debt > 0:
        unsecured_pct = unsecured_debt / total_debt

    interest_coverage: float | None = None
    if ebitda is not None and interest_expense is not None and interest_expense > 0:
        interest_coverage = ebitda / interest_expense

    # Warnings
    if net_debt_ebitda is not None and net_debt_ebitda > 7.0:
        warnings.append(
            f"Net Debt/EBITDA of {net_debt_ebitda:.1f}x exceeds 7x — elevated leverage "
            f"for an investment-grade REIT (target < 6x for IG)."
        )

    # Occupancy declining trend check (requires at least a current value)
    # Simple flag: occupancy below 90% is a concern
    if occupancy is not None and occupancy < 0.90:
        warnings.append(
            f"Occupancy {occupancy:.1%} below 90% — potential revenue pressure; "
            f"investigate lease renewal pipeline."
        )

    balance_sheet_block = {
        "net_debt": round(net_debt, 2) if net_debt is not None else None,
        "net_debt_to_ebitda": round(net_debt_ebitda, 4) if net_debt_ebitda is not None else None,
        "debt_to_assets_pct": round(debt_to_assets, 6) if debt_to_assets is not None else None,
        "unsecured_debt_pct_of_total": round(unsecured_pct, 6)
        if unsecured_pct is not None
        else None,
        "interest_coverage_ratio": round(interest_coverage, 4)
        if interest_coverage is not None
        else None,
        "weighted_avg_debt_maturity_years": wam_debt,
        "total_debt": total_debt,
        "total_assets": total_assets,
    }

    # ------------------------------------------------------------------
    # 6. Scores
    # ------------------------------------------------------------------
    affo_sustainability = _affo_sustainability_score(
        affo_payout_ratio=affo_payout_ratio,
        ss_noi_growth=ss_noi_growth,
        occupancy=occupancy,
        net_debt_ebitda=net_debt_ebitda,
    )

    composite_health = _composite_reit_health(
        affo_sustainability=affo_sustainability,
        nav_discount_pct=premium_discount_to_nav,
        interest_coverage=interest_coverage,
    )

    # ------------------------------------------------------------------
    # 7. Narrative
    # ------------------------------------------------------------------
    parts: list[str] = []
    if ffo_per_share is not None:
        parts.append(f"FFO/share ${ffo_per_share:.2f}")
    if affo_per_share is not None:
        parts.append(f"AFFO/share ${affo_per_share:.2f}")
    if affo_payout_ratio is not None:
        parts.append(f"AFFO payout {affo_payout_ratio:.0%}")
    if ss_noi_growth is not None:
        parts.append(f"SS NOI {ss_noi_growth:+.1%} YoY")
    if occupancy is not None:
        parts.append(f"occupancy {occupancy:.1%}")
    if premium_discount_to_nav is not None:
        direction = "premium" if premium_discount_to_nav > 0 else "discount"
        parts.append(f"{abs(premium_discount_to_nav):.1%} {direction} to NAV")
    if net_debt_ebitda is not None:
        parts.append(f"Net Debt/EBITDA {net_debt_ebitda:.1f}x")
    if applied_cap_rate is not None:
        parts.append(f"applied cap rate {applied_cap_rate:.2%}")

    narrative = f"{ticker}: " + "; ".join(parts) if parts else f"{ticker}: insufficient data."
    if composite_health is not None:
        narrative += f" REIT health score: {composite_health}/100."

    return {
        "ticker": ticker,
        "income": income_block,
        "affo": affo_block,
        "valuation": valuation_block,
        "operating_metrics": operating_block,
        "balance_sheet": balance_sheet_block,
        "premium_discount_to_nav_pct": valuation_block["premium_discount_to_nav_pct"],
        "affo_sustainability_score": affo_sustainability,
        "composite_reit_health_score": composite_health,
        "comparison_period": comparison_period,
        "warnings": warnings,
        "narrative": narrative,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="reit_valuation_panel",
        category=Category.SECTOR_REITS,
        one_liner=(
            "REIT KPI panel: FFO, AFFO, NAV, cap rate, same-store NOI, "
            "occupancy, composite REIT health score."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute and synthesize the four canonical REIT metric blocks — income "
            "(FFO/AFFO), valuation (NAV, P/FFO, implied cap rate), operating metrics "
            "(same-store NOI, occupancy, WALT), and balance sheet leverage — for any "
            "publicly-traded equity REIT or REOC. "
            "Mandatory for REIT-sector initiations and quarterly update reports. "
            "NAV calculation requires user-supplied cap rate assumptions."
        ),
        when_to_use=[
            "Initiating coverage or writing a quarterly update on an equity REIT or REOC.",
            "Computing NAV per share with a user-specified cap rate assumption.",
            "Evaluating AFFO payout sustainability and dividend safety.",
            "Any GICS 6010 ticker where GAAP P/E misprice value "
            "(real estate depreciation is not economic).",
        ],
        when_not_to_use=[
            "Mortgage REITs (mREITs) — mREITs are rate-sensitive financial intermediaries; "
            "use banks_sector_panel as the closest analog or refuse.",
            "Banks — use banks_sector_panel.",
            "Insurance companies — use insurance_valuation_panel.",
            "Generic industrials / tech — use dcf_engine or ratio_calculator.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                description="Company ticker, e.g. 'O', 'PLD', 'EXR'.",
                required=True,
            ),
            "financials": HelperParam(
                type="dict",
                description=(
                    "REIT-specific line items. Recognised keys: net_income, "
                    "real_estate_depreciation, gains_on_sales, losses_on_sales, "
                    "impairment_charges, recurring_capex, straight_line_rent_adj, "
                    "stock_based_comp, nareit_ffo_disclosed, dividends_paid, "
                    "ffo_prior_period, ffo_prior_year, affo_prior_period, affo_prior_year, "
                    "shares_outstanding, market_cap, current_price, total_debt, "
                    "preferred_equity, cash_and_equivalents, total_assets, unsecured_debt, "
                    "ebitda, interest_expense, weighted_avg_debt_maturity, noi_annualized, "
                    "same_store_noi_current, same_store_noi_prior_year, occupancy_rate, "
                    "walt_years, releasing_spread_pct, tenant_concentration_top10_pct, "
                    "lease_expiry_ladder."
                ),
                required=True,
            ),
            "cap_rate_assumptions": HelperParam(
                type="dict",
                description=(
                    "Required. User-supplied cap rate assumptions per decision #15. "
                    "Must contain at least one entry. Example: {'blended': 0.055} "
                    "or {'industrial': 0.045, 'office': 0.065}. "
                    "CBRE/JLL surveys require a subscription — do not hard-code; "
                    "user must supply cap rates at run time."
                ),
                required=True,
            ),
            "comparison_period": HelperParam(
                type="str",
                default=None,
                description="Comparison period label (YoY / QoQ). Informational only.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="reit_valuation_panel_output",
                type="reit_valuation_panel_output",
                description=(
                    "Full REIT KPI panel: income (FFO, AFFO, payout ratio, growth), "
                    "valuation (P/FFO, P/AFFO, NAV per share, applied cap rate, "
                    "implied cap rate, premium/discount to NAV), operating metrics "
                    "(same-store NOI growth, occupancy, WALT, re-leasing spreads, "
                    "tenant concentration, lease expiry ladder), balance sheet "
                    "(Net Debt/EBITDA, debt-to-assets, unsecured debt mix, "
                    "interest coverage, weighted average debt maturity), "
                    "AFFO sustainability score, composite REIT health score (0-100), "
                    "warnings, and narrative."
                ),
            ),
        ],
        produces_artifacts=["reit_valuation_panel_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
    skill_doc=SkillDocRef(
        path="skills/reit_valuation_panel.md",
        estimated_tokens=1900,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
