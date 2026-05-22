"""ep_sector_panel — E&P sector KPI synthesis panel.

Registered name: "ep_sector_panel"
Category: SECTOR_ENERGY

Computes and synthesizes five canonical E&P metric blocks:

  Cash flow:          EBITDAX, DACF, per-unit netback, EBITDAX margin.
  Production:         BOE/d, oil/gas/NGL mix, YoY growth.
  Capital efficiency: Capex/DACF, F&D cost/BOE, recycle ratio, FCF.
  Reserves:           1P reserves, RLI, organic RRR, reserve additions.
  Balance sheet:      Net Debt/EBITDAX, Net Debt/DACF.

Plus scenario economics (breakeven oil price, FCF sensitivities) and
a composite E&P health score (0-100).

Generic helpers (P/E, D/E, EV/EBITDA) systematically misprice E&P companies.
EBITDAX adds back exploration expense because institutional analysts treat
exploration as capex-like spending. Debt/EBITDAX is cycle-aware but misleading
at commodity price extremes — use DACF as the primary cash denominator.

Design ref: planning/2026-05-22-helpers-design-sector-modules.md §5
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
# Classification helpers
# ---------------------------------------------------------------------------

_SCENARIO_OIL_PRICES = (60.0, 80.0, 100.0)


def _cycle_phase(netback_per_boe: float | None, current_oil_price: float | None) -> str:
    """Classify E&P cycle phase from netback and oil price deck.

    Rules:
    - netback >= 30 AND oil >= 80  -> late_cycle   (peak margins)
    - netback >= 20 AND oil >= 60  -> mid_cycle
    - netback >= 10 AND oil >= 50  -> early_cycle  (recovery)
    - netback < 10 OR oil < 50     -> trough
    - insufficient data             -> unknown
    """
    if netback_per_boe is None or current_oil_price is None:
        return "unknown"
    if netback_per_boe >= 30.0 and current_oil_price >= 80.0:
        return "late_cycle"
    if netback_per_boe >= 20.0 and current_oil_price >= 60.0:
        return "mid_cycle"
    if netback_per_boe >= 10.0 and current_oil_price >= 50.0:
        return "early_cycle"
    return "trough"


def _composite_ep_health(
    *,
    netback_per_boe: float | None,
    organic_rrr: float | None,
    net_debt_to_ebitdax: float | None,
    recycle_ratio: float | None,
    reserve_life_years: float | None,
) -> float | None:
    """Weighted composite E&P health score in [0, 100].

    Component weights:
    - Netback per BOE:          30%
    - Organic RRR:              25%
    - Net Debt / EBITDAX:       20%
    - Recycle ratio:            15%
    - Reserve life index:       10%

    Returns None when no component is computable.
    """
    components: list[tuple[float, float]] = []

    if netback_per_boe is not None:
        # >= 30 -> 1.0; 20-30 -> 0.75; 10-20 -> 0.5; 0-10 -> 0.25; < 0 -> 0
        if netback_per_boe >= 30.0:
            s = 1.0
        elif netback_per_boe >= 20.0:
            s = 0.75
        elif netback_per_boe >= 10.0:
            s = 0.50
        elif netback_per_boe >= 0.0:
            s = 0.25
        else:
            s = 0.0
        components.append((s, 0.30))

    if organic_rrr is not None:
        # >= 120% -> 1.0; 100-120% -> 0.8; 80-100% -> 0.5; < 80% -> 0.2
        if organic_rrr >= 1.20:
            s = 1.0
        elif organic_rrr >= 1.00:
            s = 0.80
        elif organic_rrr >= 0.80:
            s = 0.50
        else:
            s = 0.20
        components.append((s, 0.25))

    if net_debt_to_ebitdax is not None:
        # <= 1x -> 1.0; 1-2x -> 0.75; 2-3x -> 0.4; > 3x -> 0.1
        if net_debt_to_ebitdax <= 1.0:
            s = 1.0
        elif net_debt_to_ebitdax <= 2.0:
            s = 0.75
        elif net_debt_to_ebitdax <= 3.0:
            s = 0.40
        else:
            s = 0.10
        components.append((s, 0.20))

    if recycle_ratio is not None and recycle_ratio > 0.0:
        # >= 2.5x -> 1.0; 1.5-2.5x -> 0.75; 1.0-1.5x -> 0.5; < 1.0x -> 0.2
        if recycle_ratio >= 2.5:
            s = 1.0
        elif recycle_ratio >= 1.5:
            s = 0.75
        elif recycle_ratio >= 1.0:
            s = 0.50
        else:
            s = 0.20
        components.append((s, 0.15))

    if reserve_life_years is not None:
        # >= 15 -> 1.0; 10-15 -> 0.8; 7-10 -> 0.5; < 7 -> 0.2
        if reserve_life_years >= 15.0:
            s = 1.0
        elif reserve_life_years >= 10.0:
            s = 0.80
        elif reserve_life_years >= 7.0:
            s = 0.50
        else:
            s = 0.20
        components.append((s, 0.10))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    raw = sum(s * w for s, w in components) / total_weight
    return round(raw * 100.0, 1)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    ticker: str,
    financials: dict[str, Any],
    production_data: dict[str, Any],
    reserves_data: dict[str, Any],
    hedge_book: dict[str, Any] | None = None,
    commodity_prices: dict[str, Any] | None = None,
    as_of: str | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute the institutional E&P sector KPI panel.

    Args:
        ticker: Company ticker, e.g. "XOM".
        financials: E&P-specific financial line items. Recognised keys (all optional):
            revenue, royalties_and_production_taxes, operating_costs,
            gathering_processing_transport, cash_g_and_a, interest_expense,
            dd_a_on_oil_gas_properties, da_excluding_dd_a_on_oil_gas,
            exploration_expense, cash_taxes,
            capex_maintenance, capex_growth,
            net_debt, cash_and_equivalents,
            production_prior_year_boe_per_day.
        production_data: Production metrics. Recognised keys:
            boe_per_day, oil_pct, gas_pct, ngl_pct.
        reserves_data: Reserves data. Recognised keys:
            proved_reserves_boe, proved_developed_reserves_boe,
            reserves_added_organic_boe, reserves_added_acquisitions_boe,
            reserves_added_revisions_boe.
        hedge_book: Optional hedge book. Recognised keys:
            hedged_production_pct, hedge_realized_price, spot_price,
            mtm_value.
        commodity_prices: Optional commodity price context. Recognised keys:
            wti_current, brent_current, henry_hub_current,
            realized_oil, realized_gas, realized_ngl.
        as_of: Period label or ISO date, e.g. "2026-Q1" or "2026-03-31".
        data_as_of: ISO date for data freshness.
        source_provenance: Upstream citation IDs.

    Returns:
        Structured dict with production, per_unit_economics, cash_flow,
        capital_efficiency, reserves, balance_sheet, scenario_economics,
        hedging (if provided), composite_ep_health_score (0-100),
        cycle_phase, warnings, and narrative.
    """
    warnings: list[str] = []
    f = financials
    p = production_data
    r = reserves_data
    cp = commodity_prices or {}

    # ------------------------------------------------------------------
    # 1. Production
    # ------------------------------------------------------------------
    boe_per_day: float | None = p.get("boe_per_day")
    oil_pct: float | None = p.get("oil_pct")
    gas_pct: float | None = p.get("gas_pct")
    ngl_pct: float | None = p.get("ngl_pct")
    prior_boe_per_day: float | None = f.get("production_prior_year_boe_per_day")

    yoy_growth: float | None = None
    if boe_per_day is not None and prior_boe_per_day is not None and prior_boe_per_day > 0:
        yoy_growth = (boe_per_day - prior_boe_per_day) / prior_boe_per_day

    production_block = {
        "boe_per_day": boe_per_day,
        "oil_pct": oil_pct,
        "gas_pct": gas_pct,
        "ngl_pct": ngl_pct,
        "yoy_growth_pct": round(yoy_growth, 6) if yoy_growth is not None else None,
    }

    # Annual BOE for per-unit and reserves math
    annual_boe: float | None = None
    if boe_per_day is not None:
        annual_boe = boe_per_day * 365.0

    # ------------------------------------------------------------------
    # 2. Cash-flow block and EBITDAX
    # ------------------------------------------------------------------
    revenue: float | None = f.get("revenue")
    royalties: float | None = f.get("royalties_and_production_taxes")
    operating_costs: float | None = f.get("operating_costs")
    gathering: float | None = f.get("gathering_processing_transport")
    cash_ga: float | None = f.get("cash_g_and_a")
    interest_expense: float | None = f.get("interest_expense")
    dda: float | None = f.get("dd_a_on_oil_gas_properties")
    da_other: float | None = f.get("da_excluding_dd_a_on_oil_gas", 0.0)
    exploration_expense: float | None = f.get("exploration_expense")
    cash_taxes: float | None = f.get("cash_taxes")

    # Whether the five base operating-cost lines are available (sufficient for EBITDAX)
    _da_total = (dda or 0.0) + (da_other or 0.0)
    _base_costs_known = all(
        v is not None for v in [revenue, royalties, operating_costs, gathering, cash_ga]
    )

    # EBITDAX = revenue - royalties - opex - gathering - G&A
    # (Both D&A and exploration expense are added back above the EBITDAX line.)
    ebitdax: float | None = None
    if _base_costs_known:
        ebitdax = (
            (revenue or 0.0)
            - (royalties or 0.0)
            - (operating_costs or 0.0)
            - (gathering or 0.0)
            - (cash_ga or 0.0)
        )

    # EBITDA = EBITDAX - exploration_expense
    ebitda: float | None = None
    if ebitdax is not None and exploration_expense is not None:
        ebitda = ebitdax - exploration_expense

    # EBIT = EBITDA - total D&A
    ebit: float | None = None
    if ebitda is not None:
        ebit = ebitda - _da_total

    # DACF = EBITDAX - interest - taxes
    dacf: float | None = None
    if ebitdax is not None and interest_expense is not None and cash_taxes is not None:
        dacf = ebitdax - interest_expense - cash_taxes

    ebitdax_margin: float | None = None
    if ebitdax is not None and revenue is not None and revenue > 0:
        ebitdax_margin = ebitdax / revenue

    cash_flow_block = {
        "revenue": revenue,
        "royalties_and_production_taxes": royalties,
        "operating_costs": operating_costs,
        "gathering_processing_transport": gathering,
        "cash_g_and_a": cash_ga,
        "interest_expense": interest_expense,
        "ebitdax": ebitdax,
        "exploration_expense": exploration_expense,
        "ebitda": ebitda,
        "ebit": ebit,
        "dacf": dacf,
    }

    # ------------------------------------------------------------------
    # 3. Per-unit economics
    # ------------------------------------------------------------------
    realized_price_per_boe: float | None = None
    if revenue is not None and annual_boe is not None and annual_boe > 0:
        realized_price_per_boe = revenue / annual_boe

    royalties_per_boe: float | None = None
    if royalties is not None and annual_boe is not None and annual_boe > 0:
        royalties_per_boe = royalties / annual_boe

    lifting_costs_per_boe: float | None = None
    if operating_costs is not None and annual_boe is not None and annual_boe > 0:
        lifting_costs_per_boe = operating_costs / annual_boe

    gathering_per_boe: float | None = None
    if gathering is not None and annual_boe is not None and annual_boe > 0:
        gathering_per_boe = gathering / annual_boe

    ga_per_boe: float | None = None
    if cash_ga is not None and annual_boe is not None and annual_boe > 0:
        ga_per_boe = cash_ga / annual_boe

    # Netback = realized price - royalties - lifting - gathering - G&A
    netback_per_boe: float | None = None
    _per_unit_known = all(
        v is not None
        for v in [
            realized_price_per_boe,
            royalties_per_boe,
            lifting_costs_per_boe,
            gathering_per_boe,
            ga_per_boe,
        ]
    )
    if _per_unit_known:
        netback_per_boe = (
            (realized_price_per_boe or 0.0)
            - (royalties_per_boe or 0.0)
            - (lifting_costs_per_boe or 0.0)
            - (gathering_per_boe or 0.0)
            - (ga_per_boe or 0.0)
        )

    # Warning: negative netback at oil > $60
    current_oil = cp.get("wti_current") or cp.get("realized_oil")
    if (
        netback_per_boe is not None
        and netback_per_boe < 0
        and current_oil is not None
        and current_oil > 60.0
    ):
        warnings.append(
            f"Negative netback (${netback_per_boe:.2f}/BOE) with WTI > $60 — "
            "suggests structural cost problem or significant one-off."
        )

    # AISC per BOE (production cost + maintenance capex + G&A allocation)
    capex_maintenance: float | None = f.get("capex_maintenance")
    aisc_per_boe: float | None = None
    if (
        operating_costs is not None
        and royalties is not None
        and capex_maintenance is not None
        and cash_ga is not None
        and annual_boe is not None
        and annual_boe > 0
    ):
        aisc_per_boe = (operating_costs + royalties + capex_maintenance + cash_ga) / annual_boe

    per_unit_block = {
        "realized_price_per_boe": round(realized_price_per_boe, 6)
        if realized_price_per_boe is not None
        else None,
        "royalties_per_boe": round(royalties_per_boe, 6) if royalties_per_boe is not None else None,
        "lifting_costs_per_boe": round(lifting_costs_per_boe, 6)
        if lifting_costs_per_boe is not None
        else None,
        "gathering_processing_per_boe": round(gathering_per_boe, 6)
        if gathering_per_boe is not None
        else None,
        "g_and_a_per_boe": round(ga_per_boe, 6) if ga_per_boe is not None else None,
        "netback_per_boe": round(netback_per_boe, 6) if netback_per_boe is not None else None,
        "aisc_per_boe": round(aisc_per_boe, 6) if aisc_per_boe is not None else None,
        "ebitdax_margin_pct": round(ebitdax_margin, 6) if ebitdax_margin is not None else None,
    }

    # Warning: AISC > $50/BOE
    if aisc_per_boe is not None and aisc_per_boe > 50.0:
        warnings.append(
            f"AISC ${aisc_per_boe:.2f}/BOE exceeds $50 threshold — "
            "high-cost operator; re-evaluate capital allocation at downside price scenarios."
        )

    # ------------------------------------------------------------------
    # 4. Capital efficiency
    # ------------------------------------------------------------------
    capex_growth: float | None = f.get("capex_growth")

    fcf_maintenance: float | None = None
    if dacf is not None and capex_maintenance is not None:
        fcf_maintenance = dacf - capex_maintenance

    fcf_total: float | None = None
    if dacf is not None and capex_maintenance is not None and capex_growth is not None:
        fcf_total = dacf - capex_maintenance - capex_growth

    reinvestment_rate: float | None = None
    if dacf is not None and dacf > 0 and capex_maintenance is not None and capex_growth is not None:
        reinvestment_rate = (capex_maintenance + capex_growth) / dacf

    # F&D cost = capex_growth / organic reserves added
    reserves_added_organic: float | None = r.get("reserves_added_organic_boe")
    reserves_added_acquisitions: float | None = r.get("reserves_added_acquisitions_boe", 0.0)
    reserves_added_revisions: float | None = r.get("reserves_added_revisions_boe", 0.0)

    fd_cost_per_boe: float | None = None
    _total_organic_for_fd = (reserves_added_organic or 0.0) + (reserves_added_acquisitions or 0.0)
    if capex_growth is not None and _total_organic_for_fd > 0:
        fd_cost_per_boe = capex_growth / _total_organic_for_fd

    recycle_ratio: float | None = None
    if netback_per_boe is not None and fd_cost_per_boe is not None and fd_cost_per_boe > 0:
        recycle_ratio = netback_per_boe / fd_cost_per_boe

    capital_efficiency_block = {
        "capex_maintenance": capex_maintenance,
        "capex_growth": capex_growth,
        "fcf_maintenance": fcf_maintenance,
        "fcf_total": fcf_total,
        "reinvestment_rate_pct": round(reinvestment_rate, 6)
        if reinvestment_rate is not None
        else None,
        "fd_cost_per_boe": round(fd_cost_per_boe, 6) if fd_cost_per_boe is not None else None,
        "recycle_ratio": round(recycle_ratio, 6) if recycle_ratio is not None else None,
    }

    # ------------------------------------------------------------------
    # 5. Reserves
    # ------------------------------------------------------------------
    proved_reserves: float | None = r.get("proved_reserves_boe")
    proved_developed: float | None = r.get("proved_developed_reserves_boe")

    total_reserves_added: float | None = None
    if reserves_added_organic is not None:
        total_reserves_added = (
            (reserves_added_organic or 0.0)
            + (reserves_added_acquisitions or 0.0)
            + (reserves_added_revisions or 0.0)
        )

    # RRR = total reserves added / annual production
    rrr: float | None = None
    if total_reserves_added is not None and annual_boe is not None and annual_boe > 0:
        rrr = total_reserves_added / annual_boe

    # Organic RRR = (organic + revisions) / annual production
    organic_rrr: float | None = None
    if (
        reserves_added_organic is not None
        and reserves_added_revisions is not None
        and annual_boe is not None
        and annual_boe > 0
    ):
        organic_rrr = (
            (reserves_added_organic or 0.0) + (reserves_added_revisions or 0.0)
        ) / annual_boe

    # Reserve Life Index = proved reserves / annual production
    rli: float | None = None
    if proved_reserves is not None and annual_boe is not None and annual_boe > 0:
        rli = proved_reserves / annual_boe

    proved_developed_pct: float | None = None
    if proved_developed is not None and proved_reserves is not None and proved_reserves > 0:
        proved_developed_pct = proved_developed / proved_reserves

    # Warning: RRR < 100%
    if organic_rrr is not None and organic_rrr < 1.0:
        warnings.append(
            f"Organic RRR {organic_rrr:.1%} — below 100%; company is drawing down reserves "
            "faster than replacing them through the drill bit."
        )

    reserves_block = {
        "proved_reserves_boe": proved_reserves,
        "proved_developed_pct": round(proved_developed_pct, 4)
        if proved_developed_pct is not None
        else None,
        "reserves_added_organic": reserves_added_organic,
        "reserves_added_acquisitions": reserves_added_acquisitions,
        "reserves_added_revisions": reserves_added_revisions,
        "total_reserves_added": total_reserves_added,
        "reserve_life_index_years": round(rli, 4) if rli is not None else None,
        "reserves_replacement_ratio_pct": round(rrr, 6) if rrr is not None else None,
        "organic_rrr_pct": round(organic_rrr, 6) if organic_rrr is not None else None,
    }

    # ------------------------------------------------------------------
    # 6. Balance sheet
    # ------------------------------------------------------------------
    net_debt: float | None = f.get("net_debt")

    net_debt_to_ebitdax: float | None = None
    if net_debt is not None and ebitdax is not None and ebitdax > 0:
        net_debt_to_ebitdax = net_debt / ebitdax

    net_debt_to_dacf: float | None = None
    if net_debt is not None and dacf is not None and dacf > 0:
        net_debt_to_dacf = net_debt / dacf

    # Warning: Net Debt/EBITDAX > 2x (IG threshold)
    rating_tag: str | None = f.get("rating_tag")
    is_ig = rating_tag is None or rating_tag.lower() in ("ig", "investment_grade", "")
    if net_debt_to_ebitdax is not None and net_debt_to_ebitdax > 2.0 and is_ig:
        warnings.append(
            f"Net Debt/EBITDAX {net_debt_to_ebitdax:.2f}x exceeds 2x IG target — "
            "balance sheet stress risk at downturn commodity prices."
        )

    balance_sheet_block = {
        "net_debt": net_debt,
        "net_debt_to_ebitdax": round(net_debt_to_ebitdax, 6)
        if net_debt_to_ebitdax is not None
        else None,
        "net_debt_to_dacf": round(net_debt_to_dacf, 6) if net_debt_to_dacf is not None else None,
    }

    # ------------------------------------------------------------------
    # 7. Scenario economics (commodity sensitivity)
    # ------------------------------------------------------------------
    breakeven_oil: float | None = None
    fcf_scenarios: dict[str, float | None] = {}

    if (
        revenue is not None
        and ebitdax is not None
        and capex_maintenance is not None
        and boe_per_day is not None
        and oil_pct is not None
        and current_oil is not None
        and current_oil > 0
        and annual_boe is not None
        and annual_boe > 0
    ):
        oil_annual_boe = annual_boe * (oil_pct or 0.0)

        if oil_annual_boe > 0:
            for scenario_price in _SCENARIO_OIL_PRICES:
                price_delta = scenario_price - current_oil
                delta_rev = price_delta * oil_annual_boe
                scenario_ebitdax = ebitdax + delta_rev
                scenario_dacf: float | None = None
                if interest_expense is not None and cash_taxes is not None:
                    scenario_dacf = scenario_ebitdax - interest_expense - cash_taxes
                    scenario_fcf = scenario_dacf - capex_maintenance
                    fcf_scenarios[f"fcf_at_{int(scenario_price)}"] = round(scenario_fcf, 0)
                else:
                    fcf_scenarios[f"fcf_at_{int(scenario_price)}"] = None

            # Breakeven: solve fcf_maintenance = 0 → dacf = capex_maintenance
            # dacf = ebitdax - interest - taxes = 0 + delta_ebitdax
            # ebitdax + delta_rev - interest - taxes = capex_maintenance
            if interest_expense is not None and cash_taxes is not None:
                # target_ebitdax = capex_maintenance + interest + taxes
                target_ebitdax = capex_maintenance + interest_expense + cash_taxes
                # delta_rev = oil_annual_boe * (breakeven - current_oil)
                # ebitdax + oil_annual_boe * (breakeven - current_oil) = target_ebitdax
                # breakeven = current_oil + (target_ebitdax - ebitdax) / oil_annual_boe
                breakeven_oil = current_oil + (target_ebitdax - ebitdax) / oil_annual_boe
                breakeven_oil = round(breakeven_oil, 2)

    scenario_economics_block = {
        "current_oil_price": current_oil,
        "breakeven_oil_price": breakeven_oil,
        **fcf_scenarios,
    }

    # ------------------------------------------------------------------
    # 8. Hedging block
    # ------------------------------------------------------------------
    hedging_block: dict[str, Any] | None = None
    if hedge_book:
        hedged_pct = hedge_book.get("hedged_production_pct")
        hedge_price = hedge_book.get("hedge_realized_price")
        spot = hedge_book.get("spot_price") or current_oil
        mtm = hedge_book.get("mtm_value")

        hedge_vs_spot: float | None = None
        if hedge_price is not None and spot is not None and spot > 0:
            hedge_vs_spot = hedge_price - spot

        hedging_block = {
            "hedged_production_pct": hedged_pct,
            "hedge_realized_price": hedge_price,
            "spot_price_reference": spot,
            "hedge_vs_spot": round(hedge_vs_spot, 2) if hedge_vs_spot is not None else None,
            "mtm_value": mtm,
        }

    # ------------------------------------------------------------------
    # 9. Cycle phase and composite health score
    # ------------------------------------------------------------------
    cycle_phase = _cycle_phase(netback_per_boe, current_oil)

    health_score = _composite_ep_health(
        netback_per_boe=netback_per_boe,
        organic_rrr=organic_rrr,
        net_debt_to_ebitdax=net_debt_to_ebitdax,
        recycle_ratio=recycle_ratio,
        reserve_life_years=rli,
    )

    # ------------------------------------------------------------------
    # 10. Narrative
    # ------------------------------------------------------------------
    parts: list[str] = []
    if boe_per_day is not None:
        parts.append(f"{boe_per_day:,.0f} BOE/d production")
    if oil_pct is not None:
        parts.append(f"{oil_pct:.0%} oil")
    if netback_per_boe is not None:
        parts.append(f"netback ${netback_per_boe:.2f}/BOE")
    if dacf is not None:
        parts.append(f"DACF {dacf:,.0f}")
    if organic_rrr is not None:
        parts.append(f"organic RRR {organic_rrr:.1%}")
    if rli is not None:
        parts.append(f"RLI {rli:.1f}y")
    if net_debt_to_ebitdax is not None:
        parts.append(f"Net Debt/EBITDAX {net_debt_to_ebitdax:.2f}x")
    if cycle_phase != "unknown":
        parts.append(f"cycle: {cycle_phase}")

    narrative = f"{ticker}: " + "; ".join(parts) if parts else f"{ticker}: insufficient data."
    if health_score is not None:
        narrative += f" E&P health score: {health_score}/100."

    result: dict[str, Any] = {
        "ticker": ticker,
        "as_of": as_of or datetime.date.today().isoformat(),
        "production": production_block,
        "per_unit_economics": per_unit_block,
        "cash_flow": cash_flow_block,
        "capital_efficiency": capital_efficiency_block,
        "reserves": reserves_block,
        "balance_sheet": balance_sheet_block,
        "scenario_economics": scenario_economics_block,
        "composite_ep_health_score": health_score,
        "cycle_phase": cycle_phase,
        "warnings": warnings,
        "narrative": narrative,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    if hedging_block is not None:
        result["hedging"] = hedging_block

    return result


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="ep_sector_panel",
        category=Category.SECTOR_ENERGY,
        one_liner=(
            "E&P sector KPI panel: EBITDAX, DACF, netback/BOE, F&D cost, "
            "RRR, reserve life, composite E&P health score."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute and synthesize five canonical E&P metric blocks — cash flow "
            "(EBITDAX/DACF), per-unit economics (netback/BOE, AISC), capital efficiency "
            "(F&D cost, recycle ratio, FCF), reserves (RRR, RLI, proved-developed %), "
            "and balance sheet (Net Debt/EBITDAX) — for any publicly-traded E&P company. "
            "Mandatory for Energy-sector initiations and quarterly update reports."
        ),
        when_to_use=[
            "Initiating coverage or writing a quarterly update on an oil/gas E&P company.",
            "Evaluating per-barrel economics: netback, AISC, lifting costs, netback/BOE trends.",
            "Assessing reserves quality: RRR, reserve life index, F&D cost, recycle ratio.",
            "Any GICS 1010 ticker where generic DCF / P/E / EV/EBITDA misprice value.",
            "Cycle-aware balance sheet analysis: Net Debt/EBITDAX at current vs downside prices.",
        ],
        when_not_to_use=[
            "Royalty/streaming companies (Franco-Nevada, Royal Gold) — use stream_dcf.",
            "LNG export terminals (Cheniere) — infrastructure play; use dcf_engine.",
            "Integrated majors where downstream/chemicals is dominant — use SOTP.",
            "Mining companies — AISC applies but use a mining-specific helper.",
            "Midstream MLPs — use dcf_engine with distributable cash flow model.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                description="Company ticker, e.g. 'XOM'.",
                required=True,
            ),
            "financials": HelperParam(
                type="dict",
                description=(
                    "E&P-specific financial line items. Recognised keys: "
                    "revenue, royalties_and_production_taxes, operating_costs, "
                    "gathering_processing_transport, cash_g_and_a, interest_expense, "
                    "dd_a_on_oil_gas_properties, da_excluding_dd_a_on_oil_gas, "
                    "exploration_expense, cash_taxes, capex_maintenance, capex_growth, "
                    "net_debt, production_prior_year_boe_per_day, rating_tag."
                ),
                required=True,
            ),
            "production_data": HelperParam(
                type="dict",
                description=(
                    "Production metrics. Recognised keys: boe_per_day, oil_pct, gas_pct, ngl_pct."
                ),
                required=True,
            ),
            "reserves_data": HelperParam(
                type="dict",
                description=(
                    "Reserves data. Recognised keys: proved_reserves_boe, "
                    "proved_developed_reserves_boe, reserves_added_organic_boe, "
                    "reserves_added_acquisitions_boe, reserves_added_revisions_boe."
                ),
                required=True,
            ),
            "hedge_book": HelperParam(
                type="dict",
                default=None,
                description=(
                    "Optional hedge book. Recognised keys: hedged_production_pct, "
                    "hedge_realized_price, spot_price, mtm_value."
                ),
                required=False,
            ),
            "commodity_prices": HelperParam(
                type="dict",
                default=None,
                description=(
                    "Optional commodity price context. Recognised keys: wti_current, "
                    "brent_current, henry_hub_current, realized_oil, realized_gas, realized_ngl."
                ),
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="ep_sector_panel_output",
                type="ep_sector_panel_output",
                description=(
                    "Full E&P KPI panel: production (BOE/d, oil/gas/NGL mix, YoY growth), "
                    "per-unit economics (realized price, royalties, lifting costs, gathering, "
                    "G&A, netback, AISC per BOE), cash flow (EBITDAX, DACF, EBITDA, FCF), "
                    "capital efficiency (F&D cost, recycle ratio, reinvestment rate), "
                    "reserves (proved, RLI, RRR, organic RRR, additions), "
                    "balance sheet (Net Debt/EBITDAX, Net Debt/DACF), "
                    "scenario economics (breakeven oil price, FCF at $60/$80/$100), "
                    "composite E&P health score (0-100), cycle phase, warnings, and narrative."
                ),
            ),
        ],
        produces_artifacts=["ep_sector_panel_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals", "pdf_ingest.10k_reserves"],
    ),
    skill_doc=SkillDocRef(
        path="skills/ep_sector_panel.md",
        estimated_tokens=2000,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
