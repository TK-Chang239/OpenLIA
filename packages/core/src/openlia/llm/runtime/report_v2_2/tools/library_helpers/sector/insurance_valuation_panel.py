"""insurance_valuation_panel — P&C and Life insurance KPI synthesis panel.

Registered name: "insurance_valuation_panel"
Category: SECTOR_INSURANCE

Computes and synthesizes insurance-specific metrics by segment type:

  P&C:   Combined ratio, loss ratio, expense ratio, reserve development,
         catastrophe load, underwriting profit/loss, float metrics.

  Life:  Embedded value, VNB, VNB margin, solvency ratio, persistency rate.

  Both:  ROE, book value per share (GAAP + tangible), investment yield,
         capital adequacy, composite insurance health score.

Generic helpers (P/E, D/E, EV/EBITDA) systematically misprice insurance.
This panel is mandatory for any Insurance initiation or quarterly update report.

Design ref: planning/2026-05-22-helpers-design-sector-modules.md §6
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

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
# Constants
# ---------------------------------------------------------------------------

# P&C combined ratio interpretation thresholds
_CR_EXCELLENT = 0.90  # < 90%: excellent underwriting
_CR_PROFITABLE = 1.00  # 90-100%: profitable underwriting
_CR_MARGINAL = 1.05  # 100-105%: marginal
_CR_STRUCTURAL_LOSS = 1.10  # 105-110%: structural underwriting loss
# > 110%: distressed

# Solvency II SCR coverage threshold
_SOLVENCY_II_HEALTHY = 1.50  # >= 150%: healthy
_SOLVENCY_II_BREACH = 1.00  # < 100%: Solvency II breach

# RBC ratio threshold for US insurers
_RBC_HEALTHY = 2.00  # >= 200%: healthy; below triggers regulatory action

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _combined_ratio_phase(cr: float) -> str:
    """Classify underwriting cycle phase from combined ratio.

    < 90%    : excellent
    90-100%  : profitable
    100-105% : marginal
    105-110% : structural_loss
    > 110%   : distressed
    """
    if cr < _CR_EXCELLENT:
        return "excellent"
    if cr < _CR_PROFITABLE:
        return "profitable"
    if cr < _CR_MARGINAL:
        return "marginal"
    if cr < _CR_STRUCTURAL_LOSS:
        return "structural_loss"
    return "distressed"


def _underwriting_cycle_phase(
    combined_ratio: float | None,
    combined_ratio_prior: float | None,
) -> str:
    """Classify underwriting cycle position.

    Hardening: CR improving (falling) year-over-year.
    Softening: CR deteriorating (rising) year-over-year.
    Stable:    CR within 1% of prior.
    Unknown:   insufficient data.
    """
    if combined_ratio is None:
        return "unknown"
    if combined_ratio_prior is None:
        return "unknown"
    delta = combined_ratio - combined_ratio_prior
    if delta < -0.01:
        return "hardening"
    if delta > 0.01:
        return "softening"
    return "stable"


def _composite_insurance_health(
    *,
    combined_ratio: float | None,
    roe: float | None,
    investment_yield: float | None,
    solvency_ratio: float | None,
    tbvps_growth: float | None,
) -> float | None:
    """Weighted composite insurance health score in [0, 100].

    Component weights:
    - Combined ratio (P&C):      30%  (inverted — lower CR = better)
    - ROE:                       25%
    - Solvency / capital:        25%
    - Investment yield:          10%
    - TBVPS growth:              10%

    When combined_ratio is None, solvency weight absorbs its share.
    Returns None when no component is computable.
    """
    components: list[tuple[float, float]] = []  # (score_0_1, weight)

    if combined_ratio is not None:
        # < 90% -> 1.0, 90-100% -> 0.75, 100-105% -> 0.45, > 105% -> 0.1
        if combined_ratio < 0.90:
            s = 1.0
        elif combined_ratio < 1.00:
            s = 0.75
        elif combined_ratio < 1.05:
            s = 0.45
        else:
            s = 0.10
        components.append((s, 0.30))

    if roe is not None:
        # > 15% -> 1.0, 10-15% -> 0.75, 5-10% -> 0.50, < 5% -> 0.15
        if roe >= 0.15:
            s = 1.0
        elif roe >= 0.10:
            s = 0.75
        elif roe >= 0.05:
            s = 0.50
        else:
            s = 0.15
        components.append((s, 0.25))

    if solvency_ratio is not None:
        # >= 200% -> 1.0, 150-200% -> 0.75, 100-150% -> 0.40, < 100% -> 0.0
        if solvency_ratio >= 2.00:
            s = 1.0
        elif solvency_ratio >= 1.50:
            s = 0.75
        elif solvency_ratio >= 1.00:
            s = 0.40
        else:
            s = 0.0
        components.append((s, 0.25))

    if investment_yield is not None:
        # > 4% -> 1.0, 3-4% -> 0.75, 2-3% -> 0.50, < 2% -> 0.25
        if investment_yield >= 0.04:
            s = 1.0
        elif investment_yield >= 0.03:
            s = 0.75
        elif investment_yield >= 0.02:
            s = 0.50
        else:
            s = 0.25
        components.append((s, 0.10))

    if tbvps_growth is not None:
        # > 10% -> 1.0, 5-10% -> 0.75, 0-5% -> 0.50, < 0% -> 0.10
        if tbvps_growth >= 0.10:
            s = 1.0
        elif tbvps_growth >= 0.05:
            s = 0.75
        elif tbvps_growth >= 0.00:
            s = 0.50
        else:
            s = 0.10
        components.append((s, 0.10))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    raw = sum(s * w for s, w in components) / total_weight
    return round(raw * 100, 1)


# ---------------------------------------------------------------------------
# P&C block
# ---------------------------------------------------------------------------


def _compute_pc_block(
    insurance_specific: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Compute P&C underwriting metrics.

    Combined ratio = loss_ratio + expense_ratio + policyholder_dividend_ratio.
    Loss ratio excludes prior-year reserve development (shows underlying loss).
    """
    premiums_earned: float | None = insurance_specific.get("premiums_earned")
    premiums_written: float | None = insurance_specific.get("premiums_written")
    losses_and_lae: float | None = insurance_specific.get("losses_and_lae")
    underwriting_expenses: float | None = insurance_specific.get("underwriting_expenses")
    policyholder_dividends: float | None = insurance_specific.get("policyholder_dividends", 0.0)
    prior_year_dev: float | None = insurance_specific.get("prior_year_reserve_development", 0.0)
    cat_losses: float | None = insurance_specific.get("catastrophe_losses_disclosed")
    reins_recoverable: float | None = insurance_specific.get("reinsurance_recoverable")

    # Premium growth YoY
    premiums_written_prior: float | None = insurance_specific.get("premiums_written_prior_year")
    premium_growth_yoy: float | None = None
    if (
        premiums_written is not None
        and premiums_written_prior is not None
        and premiums_written_prior != 0
    ):
        premium_growth_yoy = (premiums_written - premiums_written_prior) / abs(
            premiums_written_prior
        )

    # Loss ratio: adjusted for PY reserve development
    loss_ratio: float | None = None
    if losses_and_lae is not None and premiums_earned is not None and premiums_earned > 0:
        adjusted_losses = losses_and_lae - (prior_year_dev or 0.0)
        loss_ratio = adjusted_losses / premiums_earned

    # Expense ratio
    expense_ratio: float | None = None
    if underwriting_expenses is not None and premiums_earned is not None and premiums_earned > 0:
        expense_ratio = underwriting_expenses / premiums_earned

    # Policyholder dividend ratio
    pd_ratio: float | None = None
    if policyholder_dividends is not None and premiums_earned is not None and premiums_earned > 0:
        pd_ratio = policyholder_dividends / premiums_earned

    # Combined ratio
    combined_ratio: float | None = None
    if loss_ratio is not None and expense_ratio is not None:
        combined_ratio = loss_ratio + expense_ratio + (pd_ratio or 0.0)

    # Combined ratio ex-cat
    combined_ratio_ex_cat: float | None = None
    if (
        combined_ratio is not None
        and cat_losses is not None
        and premiums_earned is not None
        and premiums_earned > 0
    ):
        combined_ratio_ex_cat = combined_ratio - (cat_losses / premiums_earned)

    # Catastrophe load %
    cat_load_pct: float | None = None
    if cat_losses is not None and premiums_earned is not None and premiums_earned > 0:
        cat_load_pct = cat_losses / premiums_earned

    # Underwriting profit / loss
    underwriting_profit: float | None = None
    if combined_ratio is not None and premiums_earned is not None:
        underwriting_profit = premiums_earned * (1.0 - combined_ratio)

    # Warnings: combined ratio > 100% for current period
    if combined_ratio is not None and combined_ratio > 1.00:
        cycle_phase = _combined_ratio_phase(combined_ratio)
        warnings.append(
            f"Combined ratio {combined_ratio:.1%} > 100% — underwriting loss; "
            f"cycle phase: {cycle_phase}. Reliant on investment income for overall profitability."
        )

    # Adverse prior-year reserve development warning
    if prior_year_dev is not None and prior_year_dev > 0:
        warnings.append(
            f"Adverse prior-year reserve development ${prior_year_dev:,.0f} — "
            "suggests prior-year under-reserving. Review multi-year development trend."
        )

    # Reinsurance dependence note
    reinsurance_note: str | None = None
    if reins_recoverable is not None and premiums_written is not None and premiums_written > 0:
        reins_pct = reins_recoverable / premiums_written
        if reins_pct < 0.10:
            reinsurance_note = f"low — ~{reins_pct:.0%} net premiums ceded"
        elif reins_pct < 0.25:
            reinsurance_note = f"moderate — ~{reins_pct:.0%} net premiums ceded"
        else:
            reinsurance_note = f"high — ~{reins_pct:.0%} net premiums ceded"

    return {
        "premiums_written": premiums_written,
        "premiums_earned": premiums_earned,
        "premium_growth_yoy_pct": round(premium_growth_yoy, 6)
        if premium_growth_yoy is not None
        else None,
        "loss_ratio_pct": round(loss_ratio, 6) if loss_ratio is not None else None,
        "expense_ratio_pct": round(expense_ratio, 6) if expense_ratio is not None else None,
        "policyholder_dividend_ratio_pct": round(pd_ratio, 6) if pd_ratio is not None else None,
        "combined_ratio_pct": round(combined_ratio, 6) if combined_ratio is not None else None,
        "combined_ratio_ex_cat_pct": round(combined_ratio_ex_cat, 6)
        if combined_ratio_ex_cat is not None
        else None,
        "prior_year_reserve_development": prior_year_dev,
        "underwriting_profit": round(underwriting_profit, 2)
        if underwriting_profit is not None
        else None,
        "catastrophe_load_pct": round(cat_load_pct, 6) if cat_load_pct is not None else None,
        "reinsurance_dependence": reinsurance_note,
    }


# ---------------------------------------------------------------------------
# Life block
# ---------------------------------------------------------------------------


def _compute_life_block(
    insurance_specific: dict[str, Any],
    financials: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Compute Life insurance metrics.

    Embedded Value = Adjusted Net Worth + VIF.
    VNB Margin = NBV / APE.
    """
    gross_premiums: float | None = insurance_specific.get("gross_premiums")
    net_premiums: float | None = insurance_specific.get("net_premiums")
    benefits_and_claims: float | None = insurance_specific.get("benefits_and_claims_paid")
    change_in_reserves: float | None = insurance_specific.get("change_in_reserves")

    # Embedded value (prefer disclosed)
    ev_disclosed: float | None = insurance_specific.get("embedded_value_disclosed")
    vif_disclosed: float | None = insurance_specific.get("vif_disclosed")
    nbv_disclosed: float | None = insurance_specific.get("new_business_value_disclosed")

    shares_outstanding: float | None = financials.get("shares_outstanding_diluted")
    current_price: float | None = financials.get("current_price")

    # EV per share
    ev_per_share: float | None = None
    price_to_ev: float | None = None
    if ev_disclosed is not None and shares_outstanding is not None and shares_outstanding > 0:
        ev_per_share = ev_disclosed / shares_outstanding
        if current_price is not None and ev_per_share > 0:
            price_to_ev = current_price / ev_per_share

    # VNB margin = NBV / APE (Annual Premium Equivalent)
    # APE = regular premiums + 10% of single premiums (industry convention)
    ape: float | None = insurance_specific.get("annual_premium_equivalent")
    vnb_margin: float | None = None
    if nbv_disclosed is not None and ape is not None and ape > 0:
        vnb_margin = nbv_disclosed / ape

    # Solvency ratio
    solvency_ratio: float | None = insurance_specific.get("solvency_ratio")

    # Warnings on solvency
    if solvency_ratio is not None and solvency_ratio < _SOLVENCY_II_HEALTHY:
        if solvency_ratio < _SOLVENCY_II_BREACH:
            warnings.append(
                f"Solvency ratio {solvency_ratio:.0%} — BELOW 100% Solvency II minimum. "
                "Regulatory intervention likely."
            )
        else:
            warnings.append(
                f"Solvency ratio {solvency_ratio:.0%} — below 150% threshold; "
                "modest capital headroom. Monitor regulatory capital trend."
            )

    # Persistency rate
    persistency_rate: float | None = insurance_specific.get("persistency_rate")

    return {
        "gross_premiums": gross_premiums,
        "net_premiums": net_premiums,
        "benefits_and_claims_paid": benefits_and_claims,
        "change_in_reserves": change_in_reserves,
        "embedded_value_disclosed": ev_disclosed,
        "vif_disclosed": vif_disclosed,
        "new_business_value_nbv": nbv_disclosed,
        "annual_premium_equivalent_ape": ape,
        "vnb_margin_pct": round(vnb_margin, 6) if vnb_margin is not None else None,
        "ev_per_share": round(ev_per_share, 4) if ev_per_share is not None else None,
        "price_to_ev": round(price_to_ev, 4) if price_to_ev is not None else None,
        "solvency_ratio": solvency_ratio,
        "persistency_rate": persistency_rate,
    }


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    ticker: str,
    insurance_type: Literal["pc", "life", "composite"] = "pc",
    financials: dict[str, Any],
    insurance_specific: dict[str, Any],
    comparison_period: str | None = None,
    as_of: str | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute the institutional insurance KPI panel.

    Args:
        ticker: Company ticker, e.g. "CB", "ALL", "PRU".
        insurance_type: "pc" for P&C, "life" for Life, "composite" for both.
        financials: Common financial line items. Recognised keys:
            invested_assets, investment_income, net_realized_gains_losses,
            book_value_equity_gaap, book_value_equity_stat (optional),
            intangibles_and_goodwill, accumulated_oci (optional),
            shares_outstanding_diluted, current_price,
            net_income, avg_equity, avg_equity_prior (optional),
            tangible_book_value_prior_year (optional, for TBVPS growth).
        insurance_specific: Segment-specific line items.
          P&C keys: premiums_earned, premiums_written, losses_and_lae,
            underwriting_expenses, policyholder_dividends (optional),
            prior_year_reserve_development (optional; negative = favorable),
            catastrophe_losses_disclosed (optional),
            reinsurance_recoverable (optional),
            premiums_written_prior_year (optional, for premium growth).
          Life keys: gross_premiums, net_premiums, benefits_and_claims_paid,
            change_in_reserves, embedded_value_disclosed (optional),
            vif_disclosed (optional), new_business_value_disclosed (optional),
            annual_premium_equivalent (optional), solvency_ratio (optional),
            persistency_rate (optional).
        comparison_period: Label for comparison period (YoY / QoQ).
        as_of: Quarter label or ISO date, e.g. "2026-Q1" or "2026-03-31".
        data_as_of: ISO date for data freshness.
        source_provenance: Upstream citation IDs.

    Returns:
        Structured dict with pc/life sub-blocks (per insurance_type),
        investment_portfolio, balance_sheet, capital_adequacy,
        composite insurance health score (0-100), underwriting_cycle_phase,
        float metrics (P&C only), warnings, and narrative.
    """
    warnings: list[str] = []
    f = financials
    ispec = insurance_specific

    # ------------------------------------------------------------------
    # 1. P&C block
    # ------------------------------------------------------------------
    pc_block: dict[str, Any] | None = None
    if insurance_type in ("pc", "composite"):
        pc_block = _compute_pc_block(ispec, warnings)

    # ------------------------------------------------------------------
    # 2. Life block
    # ------------------------------------------------------------------
    life_block: dict[str, Any] | None = None
    if insurance_type in ("life", "composite"):
        life_block = _compute_life_block(ispec, f, warnings)

    # ------------------------------------------------------------------
    # 3. Investment portfolio
    # ------------------------------------------------------------------
    invested_assets: float | None = f.get("invested_assets")
    investment_income: float | None = f.get("investment_income")
    net_realized_gains: float | None = f.get("net_realized_gains_losses", 0.0)

    investment_yield: float | None = None
    if investment_income is not None and invested_assets is not None and invested_assets > 0:
        investment_yield = investment_income / invested_assets

    investment_portfolio = {
        "invested_assets": invested_assets,
        "investment_income": investment_income,
        "investment_yield_pct": round(investment_yield, 6)
        if investment_yield is not None
        else None,
        "net_realized_gains_losses": net_realized_gains,
    }

    # ------------------------------------------------------------------
    # 4. Balance sheet (GAAP + tangible book value per share)
    # ------------------------------------------------------------------
    bvps_gaap: float | None = None
    tbvps: float | None = None
    price_to_book_gaap: float | None = None
    price_to_tangible_book: float | None = None
    tbvps_growth: float | None = None

    book_equity_gaap: float | None = f.get("book_value_equity_gaap")
    book_equity_stat: float | None = f.get("book_value_equity_stat")
    intangibles: float | None = f.get("intangibles_and_goodwill", 0.0)
    accumulated_oci: float | None = f.get("accumulated_oci")
    shares_outstanding: float | None = f.get("shares_outstanding_diluted")
    current_price: float | None = f.get("current_price")

    tangible_book_value: float | None = None
    if book_equity_gaap is not None:
        if book_equity_gaap <= 0:
            warnings.append(
                f"GAAP equity negative (${book_equity_gaap:,.0f}) — "
                "per-share metrics not computable; structural impairment."
            )
        else:
            tangible_book_value = book_equity_gaap - (intangibles or 0.0)

            if shares_outstanding is not None and shares_outstanding > 0:
                bvps_gaap = book_equity_gaap / shares_outstanding
                tbvps = tangible_book_value / shares_outstanding

                if current_price is not None:
                    if bvps_gaap > 0:
                        price_to_book_gaap = current_price / bvps_gaap
                    if tbvps is not None and tbvps > 0:
                        price_to_tangible_book = current_price / tbvps

    # TBVPS growth (requires prior-year tangible BV per share)
    tangible_bv_prior: float | None = f.get("tangible_book_value_prior_year")
    if (
        tangible_book_value is not None
        and shares_outstanding is not None
        and shares_outstanding > 0
    ):
        tbvps_current = tangible_book_value / shares_outstanding
        if tangible_bv_prior is not None and tangible_bv_prior > 0:
            tbvps_prior = tangible_bv_prior / shares_outstanding
            tbvps_growth = (tbvps_current - tbvps_prior) / tbvps_prior

    balance_sheet = {
        "book_value_equity_gaap": book_equity_gaap,
        "book_value_equity_stat": book_equity_stat,
        "tangible_book_value": tangible_book_value,
        "accumulated_oci": accumulated_oci,
        "shares_outstanding_diluted": shares_outstanding,
        "book_value_per_share_gaap": round(bvps_gaap, 4) if bvps_gaap is not None else None,
        "tangible_book_value_per_share": round(tbvps, 4) if tbvps is not None else None,
        "tangible_book_value_per_share_growth_pct": round(tbvps_growth, 6)
        if tbvps_growth is not None
        else None,
        "price_to_book_gaap": round(price_to_book_gaap, 4)
        if price_to_book_gaap is not None
        else None,
        "price_to_tangible_book": round(price_to_tangible_book, 4)
        if price_to_tangible_book is not None
        else None,
    }

    # ------------------------------------------------------------------
    # 5. ROE
    # ------------------------------------------------------------------
    net_income: float | None = f.get("net_income")
    avg_equity: float | None = f.get("avg_equity")

    roe: float | None = None
    if net_income is not None and avg_equity is not None and avg_equity > 0:
        roe = net_income / avg_equity

    # ------------------------------------------------------------------
    # 6. Float metrics (P&C only)
    # ------------------------------------------------------------------
    float_block: dict[str, Any] | None = None
    if insurance_type in ("pc", "composite") and pc_block is not None:
        premiums_earned_val: float | None = ispec.get("premiums_earned")

        # Float / equity ratio (Berkshire-style)
        float_equity_ratio: float | None = None
        if invested_assets is not None and book_equity_gaap is not None and book_equity_gaap > 0:
            float_equity_ratio = invested_assets / book_equity_gaap

        # Float generation cost = (operating loss * -1) / float
        # Operating loss occurs when combined ratio > 100%
        float_cost: float | None = None
        cr_val: float | None = pc_block.get("combined_ratio_pct")
        if (
            cr_val is not None
            and cr_val > 1.00
            and premiums_earned_val is not None
            and invested_assets is not None
            and invested_assets > 0
        ):
            operating_loss = premiums_earned_val * (cr_val - 1.00)  # cost of float
            float_cost = operating_loss / invested_assets  # cost as % of float
        elif cr_val is not None and cr_val <= 1.00:
            float_cost = (
                0.0  # free float: combined <= 100% means underwriting profit subsidizes float
            )

        float_block = {
            "float_equity_ratio": round(float_equity_ratio, 4)
            if float_equity_ratio is not None
            else None,
            "float_generation_cost_pct": round(float_cost, 6) if float_cost is not None else None,
            "note": (
                "Float = invested assets; cost = underwriting loss as % of float. "
                "CR <= 100% implies free or profitable float."
            ),
        }

    # ------------------------------------------------------------------
    # 7. Capital adequacy (disclosed metrics only)
    # ------------------------------------------------------------------
    rbc_ratio: float | None = f.get("rbc_ratio_disclosed")
    solvency_ii_ratio: float | None = (
        ispec.get("solvency_ratio")
        if insurance_type in ("life", "composite")
        else f.get("solvency_ii_scr_ratio")
    )
    bcar_rating: str | None = f.get("bcar_disclosed")

    # RBC ratio warning (US P&C/Life)
    if rbc_ratio is not None and rbc_ratio < _RBC_HEALTHY:
        warnings.append(
            f"RBC ratio {rbc_ratio:.0%} — below 200% threshold; NAIC regulatory action zone."
        )

    capital_adequacy = {
        "rbc_ratio_disclosed": rbc_ratio,
        "solvency_ii_scr_ratio": solvency_ii_ratio,
        "bcar_disclosed": bcar_rating,
    }

    # ------------------------------------------------------------------
    # 8. Underwriting cycle phase (P&C)
    # ------------------------------------------------------------------
    cr_prior: float | None = ispec.get("combined_ratio_prior_year")
    cr_current: float | None = pc_block.get("combined_ratio_pct") if pc_block is not None else None
    uw_cycle = _underwriting_cycle_phase(cr_current, cr_prior)

    # ------------------------------------------------------------------
    # 9. Composite insurance health score
    # ------------------------------------------------------------------
    solvency_for_score: float | None = solvency_ii_ratio or (
        (rbc_ratio / 2.0) if rbc_ratio is not None else None  # normalise RBC to ~1.0 scale
    )
    health_score = _composite_insurance_health(
        combined_ratio=cr_current,
        roe=roe,
        investment_yield=investment_yield,
        solvency_ratio=solvency_for_score,
        tbvps_growth=tbvps_growth,
    )

    # ------------------------------------------------------------------
    # 10. Narrative
    # ------------------------------------------------------------------
    parts: list[str] = []
    if cr_current is not None:
        parts.append(f"combined ratio {cr_current:.1%}")
        ex_cat = pc_block.get("combined_ratio_ex_cat_pct") if pc_block else None
        if ex_cat is not None:
            parts.append(f"ex-cat {ex_cat:.1%}")
    if life_block is not None and life_block.get("vnb_margin_pct") is not None:
        parts.append(f"VNB margin {life_block['vnb_margin_pct']:.1%}")
    if roe is not None:
        parts.append(f"ROE {roe:.1%}")
    if bvps_gaap is not None:
        parts.append(f"BVPS ${bvps_gaap:.2f}")
    if investment_yield is not None:
        parts.append(f"investment yield {investment_yield:.2%}")
    if bcar_rating:
        parts.append(f"capital: {bcar_rating}")
    if uw_cycle != "unknown":
        parts.append(f"underwriting cycle: {uw_cycle}")

    narrative = (
        f"{ticker} ({insurance_type.upper()}): " + "; ".join(parts)
        if parts
        else f"{ticker}: insufficient data."
    )
    if health_score is not None:
        narrative += f" Insurance health score: {health_score}/100."

    return {
        "ticker": ticker,
        "insurance_type": insurance_type,
        "as_of": as_of or datetime.date.today().isoformat(),
        "pc": pc_block,
        "life": life_block,
        "float_metrics": float_block,
        "investment_portfolio": investment_portfolio,
        "balance_sheet": balance_sheet,
        "roe_pct": round(roe, 6) if roe is not None else None,
        "capital_adequacy": capital_adequacy,
        "composite_health_score": health_score,
        "underwriting_cycle_phase": uw_cycle,
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
        name="insurance_valuation_panel",
        category=Category.SECTOR_INSURANCE,
        one_liner=(
            "Insurance KPI panel: combined ratio (P&C), embedded value / VNB margin (Life), "
            "ROE, investment yield, BVPS, capital adequacy, insurance health score."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute and synthesize the canonical insurance metric blocks for P&C insurers "
            "(combined ratio, loss ratio, expense ratio, reserve development, float metrics) "
            "and Life insurers (embedded value, VNB, VNB margin, solvency ratio). "
            "Also computes cross-cutting metrics: ROE, book value per share (GAAP + tangible), "
            "investment yield, capital adequacy, and composite insurance health score. "
            "Mandatory for Insurance-sector initiations and quarterly update reports."
        ),
        when_to_use=[
            "Initiating coverage or writing a quarterly update on a P&C or Life insurer.",
            "Evaluating underwriting quality via combined ratio and reserve development.",
            "Assessing Life insurer intrinsic value via embedded value and VNB margin.",
            "Computing float quality and cost for Berkshire-style capital analysis.",
            "Any GICS 4030 ticker where generic DCF / P/E / D/E misprice value.",
        ],
        when_not_to_use=[
            "Banks and bank holding companies — use banks_sector_panel.",
            "REITs — use reit_valuation_panel.",
            "Asset managers and brokerages — use dcf_engine with appropriate margin structure.",
            "Mutual insurers (no equity) — refuse; per-share metrics are undefined.",
            "Generic industrial / tech / consumer companies — use ratio_calculator or dcf_engine.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                description="Company ticker, e.g. 'CB', 'ALL', 'PRU'.",
                required=True,
            ),
            "insurance_type": HelperParam(
                type="Literal['pc', 'life', 'composite']",
                default="pc",
                description=(
                    "Insurance segment: 'pc' for P&C only, 'life' for Life only, "
                    "'composite' for both sub-blocks."
                ),
                required=False,
            ),
            "financials": HelperParam(
                type="dict",
                description=(
                    "Common financial line items. Keys: invested_assets, investment_income, "
                    "net_realized_gains_losses (optional), book_value_equity_gaap, "
                    "book_value_equity_stat (optional), intangibles_and_goodwill, "
                    "accumulated_oci (optional), shares_outstanding_diluted, current_price, "
                    "net_income, avg_equity, tangible_book_value_prior_year (optional), "
                    "rbc_ratio_disclosed (optional), solvency_ii_scr_ratio (optional), "
                    "bcar_disclosed (optional)."
                ),
                required=True,
            ),
            "insurance_specific": HelperParam(
                type="dict",
                description=(
                    "Segment-specific line items. "
                    "P&C: premiums_earned, premiums_written, losses_and_lae, "
                    "underwriting_expenses, policyholder_dividends (opt), "
                    "prior_year_reserve_development (opt; negative = favorable), "
                    "catastrophe_losses_disclosed (opt), reinsurance_recoverable (opt), "
                    "premiums_written_prior_year (opt), combined_ratio_prior_year (opt). "
                    "Life: gross_premiums, net_premiums, benefits_and_claims_paid, "
                    "change_in_reserves, embedded_value_disclosed (opt), vif_disclosed (opt), "
                    "new_business_value_disclosed (opt), annual_premium_equivalent (opt), "
                    "solvency_ratio (opt), persistency_rate (opt)."
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
                name="insurance_valuation_panel_output",
                type="insurance_valuation_panel_output",
                description=(
                    "Insurance KPI panel with P&C sub-block (combined ratio, loss ratio, "
                    "expense ratio, reserve development, catastrophe load, underwriting profit, "
                    "float metrics), Life sub-block (embedded value, VNB, VNB margin, solvency, "
                    "persistency), investment portfolio (yield, invested assets), balance sheet "
                    "(GAAP BVPS, tangible BVPS, P/TBV), ROE, capital adequacy (RBC, Solvency II, "
                    "BCAR), composite insurance health score (0-100), underwriting cycle phase, "
                    "warnings, and narrative."
                ),
            ),
        ],
        produces_artifacts=["insurance_valuation_panel_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
    skill_doc=SkillDocRef(
        path="skills/insurance_valuation_panel.md",
        estimated_tokens=2000,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
