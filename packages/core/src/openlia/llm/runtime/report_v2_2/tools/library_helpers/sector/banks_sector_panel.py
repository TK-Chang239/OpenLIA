"""banks_sector_panel — institutional bank KPI synthesis panel.

Registered name: "banks_sector_panel"
Category: SECTOR_BANKS

Computes and synthesizes the five canonical bank metric blocks:

  Profitability:  NIM, RoTCE, ROA, ROE, efficiency ratio, fee income mix.
  Capital:        CET1, Tier 1, Total Capital, leverage ratio; buffer vs regulatory min.
  Credit quality: NCO rate, NPL ratio, ACL coverage, LLP build/release.
  Liquidity:      Loan-to-deposit ratio, wholesale funding mix.
  Cycle phase:    expansion / mid_cycle_normalizing / early_deterioration / stress / recovery.

Generic helpers (P/E, D/E, EV/EBITDA) systematically misprice banks.
This panel is mandatory for any Banks initiation or quarterly update report.

Design ref: planning/2026-05-22-helpers-design-sector-modules.md §2
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
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MIN_CET1 = 0.07  # 4.5% Pillar 1 + 2.5% conservation buffer

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _cet1_buffer_adequacy(buffer: float) -> str:
    if buffer >= 0.030:
        return "comfortable"
    if buffer >= 0.015:
        return "modest"
    if buffer >= 0.000:
        return "tight"
    return "below_minimum_regulatory_action_expected"


def _credit_cycle_phase(
    nco_rate: float | None,
    nco_prior: float | None,
    llp_yoy: float | None,
) -> str:
    """Classify credit cycle position from NCO trend and LLP YoY change.

    Rules per design §2 (heuristic):
    - NCO flat / low AND LLP yoy modest (< 20%)  -> mid_cycle_normalizing
    - NCO rising AND LLP yoy > 50%               -> early_deterioration
    - NCO at peak AND LLP building rapidly        -> stress
    - NCO falling AND reserves releasing          -> recovery
    - insufficient data                           -> unknown
    """
    if nco_rate is None:
        return "unknown"

    nco_rising = nco_prior is not None and nco_rate > nco_prior * 1.10
    nco_surging = nco_prior is not None and nco_rate > nco_prior * 1.20
    nco_falling = nco_prior is not None and nco_rate < nco_prior * 0.90
    llp_heavy = llp_yoy is not None and llp_yoy > 0.50
    llp_very_heavy = llp_yoy is not None and llp_yoy > 1.00
    llp_negative = llp_yoy is not None and llp_yoy < -0.05  # releasing

    if nco_falling and llp_negative:
        return "recovery"
    if nco_surging and llp_very_heavy:
        return "stress"
    if nco_rising and llp_heavy:
        return "early_deterioration"
    return "mid_cycle_normalizing"


def _composite_bank_health(
    *,
    cet1_buffer: float | None,
    rotce: float | None,
    efficiency_ratio: float | None,
    nco_rate: float | None,
    npl_ratio: float | None,
    acl_coverage: float | None,
) -> float | None:
    """Weighted composite bank health score in [0, 100].

    Component weights:
    - Capital adequacy (CET1 buffer):  30%
    - Profitability (RoTCE):           25%
    - Efficiency ratio (inverted):     20%
    - Asset quality (NCO rate):        15%
    - Coverage ratio (ACL/NPL):        10%

    Returns None when no component is computable.
    """
    components: list[tuple[float, float]] = []  # (score_0_1, weight)

    if cet1_buffer is not None:
        # comfortable (>=300bps) -> 1.0, modest -> 0.7, tight (0-150bps) -> 0.4, negative -> 0
        if cet1_buffer >= 0.030:
            s = 1.0
        elif cet1_buffer >= 0.015:
            s = 0.70
        elif cet1_buffer >= 0.000:
            s = 0.40
        else:
            s = 0.0
        components.append((s, 0.30))

    if rotce is not None:
        # > 15% -> 1.0, 10-15% -> 0.7, 5-10% -> 0.4, < 5% -> 0.1
        if rotce >= 0.15:
            s = 1.0
        elif rotce >= 0.10:
            s = 0.70
        elif rotce >= 0.05:
            s = 0.40
        else:
            s = 0.10
        components.append((s, 0.25))

    if efficiency_ratio is not None:
        # < 50% -> 1.0, 50-60% -> 0.75, 60-70% -> 0.5, > 70% -> 0.2
        if efficiency_ratio < 0.50:
            s = 1.0
        elif efficiency_ratio < 0.60:
            s = 0.75
        elif efficiency_ratio < 0.70:
            s = 0.50
        else:
            s = 0.20
        components.append((s, 0.20))

    if nco_rate is not None:
        # < 25bps -> 1.0, 25-50bps -> 0.8, 50-100bps -> 0.5, > 100bps -> 0.2
        if nco_rate < 0.0025:
            s = 1.0
        elif nco_rate < 0.0050:
            s = 0.80
        elif nco_rate < 0.0100:
            s = 0.50
        else:
            s = 0.20
        components.append((s, 0.15))

    if acl_coverage is not None:
        # > 2.5x -> 1.0, 1.5-2.5x -> 0.75, 1.0-1.5x -> 0.5, < 1.0x -> 0.2
        if acl_coverage > 2.5:
            s = 1.0
        elif acl_coverage >= 1.5:
            s = 0.75
        elif acl_coverage >= 1.0:
            s = 0.50
        else:
            s = 0.20
        components.append((s, 0.10))

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
    as_of: str,
    regulatory_min_cet1: float | None = None,
    comparison_period: str | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute the institutional bank KPI panel.

    Args:
        ticker: Company ticker, e.g. "JPM".
        financials: Bank-specific line items dict. Recognised keys (all optional):
            interest_income, interest_expense, avg_earning_assets,
            non_interest_income, non_interest_expense,
            net_income, avg_total_assets, avg_common_equity,
            avg_tangible_common_equity,
            cet1_ratio, tier1_ratio, total_capital_ratio, leverage_ratio,
            risk_weighted_assets,
            net_charge_offs, avg_loans, total_loans,
            nonperforming_loans, allowance_for_credit_losses,
            loan_loss_provision, loan_loss_provision_prior_year,
            nco_rate_prior (prior period NCO rate for cycle comparison),
            total_deposits, wholesale_funding,
            deposit_cost, avg_interest_bearing_deposits.
        as_of: Quarter label, e.g. "2026-Q1" or "2026-03-31".
        regulatory_min_cet1: CET1 regulatory minimum as decimal. Default 7.0% (4.5%+2.5%).
            Pass a higher value for G-SIBs with surcharge (e.g. 0.09 for 9%).
        comparison_period: Label for comparison period (YoY / QoQ). Informational only.
        data_as_of: ISO date for data freshness.
        source_provenance: Upstream citation IDs.

    Returns:
        Structured dict with profitability, capital_adequacy, credit_quality,
        liquidity, cycle_phase, composite_health_score (0-100), warnings, and narrative.
    """
    warnings: list[str] = []
    f = financials  # alias

    reg_min = regulatory_min_cet1 if regulatory_min_cet1 is not None else _DEFAULT_MIN_CET1

    # ------------------------------------------------------------------
    # 1. Profitability
    # ------------------------------------------------------------------
    interest_income: float | None = f.get("interest_income")
    interest_expense: float | None = f.get("interest_expense")
    avg_earning_assets: float | None = f.get("avg_earning_assets")
    non_interest_income: float | None = f.get("non_interest_income")
    non_interest_expense: float | None = f.get("non_interest_expense")
    net_income: float | None = f.get("net_income")
    avg_total_assets: float | None = f.get("avg_total_assets")
    avg_common_equity: float | None = f.get("avg_common_equity")
    avg_tce: float | None = f.get("avg_tangible_common_equity")

    nii: float | None = None
    if interest_income is not None and interest_expense is not None:
        nii = interest_income - interest_expense

    total_revenue: float | None = None
    if nii is not None and non_interest_income is not None:
        total_revenue = nii + non_interest_income

    nim: float | None = None
    if nii is not None and avg_earning_assets is not None and avg_earning_assets > 0:
        nim = nii / avg_earning_assets

    fee_income_pct: float | None = None
    if non_interest_income is not None and total_revenue is not None and total_revenue > 0:
        fee_income_pct = non_interest_income / total_revenue

    efficiency_ratio: float | None = None
    if non_interest_expense is not None and total_revenue is not None and total_revenue > 0:
        efficiency_ratio = non_interest_expense / total_revenue

    roa: float | None = None
    if net_income is not None and avg_total_assets is not None and avg_total_assets > 0:
        roa = net_income / avg_total_assets

    roe: float | None = None
    if net_income is not None and avg_common_equity is not None and avg_common_equity > 0:
        roe = net_income / avg_common_equity

    rotce: float | None = None
    if net_income is not None and avg_tce is not None and avg_tce > 0:
        rotce = net_income / avg_tce

    profitability = {
        "net_interest_income": nii,
        "non_interest_income": non_interest_income,
        "total_revenue": total_revenue,
        "net_interest_margin_pct": round(nim, 6) if nim is not None else None,
        "fee_income_pct_of_revenue": round(fee_income_pct, 6)
        if fee_income_pct is not None
        else None,
        "net_income": net_income,
        "rotce_pct": round(rotce, 6) if rotce is not None else None,
        "roa_pct": round(roa, 6) if roa is not None else None,
        "roe_pct": round(roe, 6) if roe is not None else None,
        "efficiency_ratio_pct": round(efficiency_ratio, 6)
        if efficiency_ratio is not None
        else None,
    }

    # ------------------------------------------------------------------
    # 2. Capital adequacy
    # ------------------------------------------------------------------
    cet1: float | None = f.get("cet1_ratio")
    tier1: float | None = f.get("tier1_ratio")
    total_cap: float | None = f.get("total_capital_ratio")
    leverage: float | None = f.get("leverage_ratio")

    cet1_buffer: float | None = None
    buffer_adequacy: str | None = None
    if cet1 is not None:
        cet1_buffer = round(cet1 - reg_min, 6)
        buffer_adequacy = _cet1_buffer_adequacy(cet1_buffer)
        if cet1_buffer < 0.010:
            warnings.append(
                f"CET1 {cet1:.1%} is within 100bps of regulatory minimum "
                f"{reg_min:.1%} — buffer adequacy: {buffer_adequacy}."
            )

    capital_adequacy = {
        "cet1_ratio_pct": cet1,
        "tier1_ratio_pct": tier1,
        "total_capital_ratio_pct": total_cap,
        "leverage_ratio_pct": leverage,
        "cet1_buffer_vs_minimum": cet1_buffer,
        "regulatory_minimum_cet1": reg_min,
        "buffer_adequacy": buffer_adequacy,
    }

    # ------------------------------------------------------------------
    # 3. Credit quality
    # ------------------------------------------------------------------
    net_charge_offs: float | None = f.get("net_charge_offs")
    avg_loans: float | None = f.get("avg_loans")
    total_loans: float | None = f.get("total_loans")
    npl: float | None = f.get("nonperforming_loans")
    acl: float | None = f.get("allowance_for_credit_losses")
    llp: float | None = f.get("loan_loss_provision")
    llp_prior: float | None = f.get("loan_loss_provision_prior_year")
    nco_rate_prior: float | None = f.get("nco_rate_prior")
    total_deposits: float | None = f.get("total_deposits")

    nco_rate: float | None = None
    loan_base = avg_loans if avg_loans is not None else total_loans
    if net_charge_offs is not None and loan_base is not None and loan_base > 0:
        nco_rate = net_charge_offs / loan_base

    npl_ratio: float | None = None
    if npl is not None and total_loans is not None and total_loans > 0:
        npl_ratio = npl / total_loans

    acl_coverage: float | None = None
    if acl is not None and npl is not None and npl > 0:
        acl_coverage = acl / npl

    acl_to_loans: float | None = None
    if acl is not None and total_loans is not None and total_loans > 0:
        acl_to_loans = acl / total_loans

    llp_yoy: float | None = None
    if llp is not None and llp_prior is not None and llp_prior != 0:
        llp_yoy = (llp - llp_prior) / abs(llp_prior)

    # NCO surge warning: > 20% QoQ increase
    if nco_rate is not None and nco_rate_prior is not None and nco_rate_prior > 0:
        nco_change = (nco_rate - nco_rate_prior) / nco_rate_prior
        if nco_change > 0.20:
            warnings.append(
                f"NCO rate surge: {nco_rate:.2%} vs prior {nco_rate_prior:.2%} "
                f"(+{nco_change:.0%} QoQ) — potential credit deterioration signal."
            )

    # Cycle phase
    cycle_phase = _credit_cycle_phase(nco_rate, nco_rate_prior, llp_yoy)

    credit_quality = {
        "acl_to_loans_pct": round(acl_to_loans, 6) if acl_to_loans is not None else None,
        "nco_rate_pct": round(nco_rate, 6) if nco_rate is not None else None,
        "npl_ratio_pct": round(npl_ratio, 6) if npl_ratio is not None else None,
        "acl_coverage_ratio": round(acl_coverage, 4) if acl_coverage is not None else None,
        "loan_loss_provision": llp,
        "loan_loss_provision_yoy_change_pct": round(llp_yoy, 6) if llp_yoy is not None else None,
        "credit_cycle_phase": cycle_phase,
    }

    # ------------------------------------------------------------------
    # 4. Liquidity / funding
    # ------------------------------------------------------------------
    wholesale_funding: float | None = f.get("wholesale_funding")
    deposit_cost: float | None = f.get("deposit_cost")
    avg_ib_deposits: float | None = f.get("avg_interest_bearing_deposits")

    ldr: float | None = None
    if total_loans is not None and total_deposits is not None and total_deposits > 0:
        ldr = total_loans / total_deposits

    wholesale_pct: float | None = None
    if wholesale_funding is not None and total_deposits is not None and total_deposits > 0:
        wholesale_pct = wholesale_funding / total_deposits

    deposit_cost_pct: float | None = None
    if deposit_cost is not None and avg_ib_deposits is not None and avg_ib_deposits > 0:
        deposit_cost_pct = deposit_cost / avg_ib_deposits

    liquidity = {
        "loan_to_deposit_ratio": round(ldr, 6) if ldr is not None else None,
        "wholesale_funding_pct_of_deposits": round(wholesale_pct, 6)
        if wholesale_pct is not None
        else None,
        "deposit_cost_pct": round(deposit_cost_pct, 6) if deposit_cost_pct is not None else None,
    }

    # ------------------------------------------------------------------
    # 5. Composite health score
    # ------------------------------------------------------------------
    health_score = _composite_bank_health(
        cet1_buffer=cet1_buffer,
        rotce=rotce,
        efficiency_ratio=efficiency_ratio,
        nco_rate=nco_rate,
        npl_ratio=None,  # NCO is primary quality signal; NPL is secondary
        acl_coverage=acl_coverage,
    )

    # ------------------------------------------------------------------
    # 6. Narrative
    # ------------------------------------------------------------------
    parts: list[str] = []
    if nim is not None:
        parts.append(f"NIM {nim:.2%}")
    if rotce is not None:
        parts.append(f"RoTCE {rotce:.1%}")
    if efficiency_ratio is not None:
        parts.append(f"efficiency {efficiency_ratio:.1%}")
    if cet1 is not None:
        parts.append(f"CET1 {cet1:.1%} ({buffer_adequacy} buffer)")
    if nco_rate is not None:
        parts.append(f"NCO {nco_rate:.0%}")
    if cycle_phase != "unknown":
        parts.append(f"cycle: {cycle_phase}")

    narrative = f"{ticker}: " + "; ".join(parts) if parts else f"{ticker}: insufficient data."
    if health_score is not None:
        narrative += f" Bank health score: {health_score}/100."

    return {
        "ticker": ticker,
        "as_of": as_of,
        "profitability": profitability,
        "capital_adequacy": capital_adequacy,
        "credit_quality": credit_quality,
        "liquidity": liquidity,
        "composite_health_score": health_score,
        "cycle_phase": cycle_phase,
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
        name="banks_sector_panel",
        category=Category.SECTOR_BANKS,
        one_liner=(
            "Institutional bank KPI panel: NIM, RoTCE, CET1, efficiency ratio, "
            "NCO, credit cycle, composite bank health score."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute and synthesize the five canonical bank metric blocks — profitability, "
            "capital adequacy, credit quality, liquidity, and credit-cycle phase — for any "
            "publicly-traded commercial bank, savings institution, or bank holding company. "
            "Mandatory for Banks-sector initiations and quarterly update reports."
        ),
        when_to_use=[
            "Initiating coverage or writing a quarterly update on a bank or bank holding company.",
            "Evaluating capital adequacy (CET1 buffer) and buffer vs regulatory minimums.",
            "Assessing credit quality trajectory (NCO rate, NPL ratio, ACL coverage) "
            "and credit-cycle positioning.",
            "Any GICS 4010-4020 ticker where generic DCF / P/E / EV/EBITDA misprice value.",
        ],
        when_not_to_use=[
            "Non-bank financials (insurance) — use insurance_valuation_panel.",
            "REITs — use reit_valuation_panel.",
            "Asset managers and brokerages — use dcf_engine with appropriate margin structure.",
            "Generic industrial / tech / consumer companies — use ratio_calculator or dcf_engine.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                description="Company ticker, e.g. 'JPM'.",
                required=True,
            ),
            "financials": HelperParam(
                type="dict",
                description=(
                    "Bank-specific line items. Recognised keys: interest_income, "
                    "interest_expense, avg_earning_assets, non_interest_income, "
                    "non_interest_expense, net_income, avg_total_assets, avg_common_equity, "
                    "avg_tangible_common_equity, cet1_ratio, tier1_ratio, total_capital_ratio, "
                    "leverage_ratio, net_charge_offs, avg_loans, total_loans, "
                    "nonperforming_loans, allowance_for_credit_losses, loan_loss_provision, "
                    "loan_loss_provision_prior_year, nco_rate_prior, total_deposits, "
                    "wholesale_funding, deposit_cost, avg_interest_bearing_deposits."
                ),
                required=True,
            ),
            "as_of": HelperParam(
                type="str",
                description="Quarter label or ISO date, e.g. '2026-Q1' or '2026-03-31'.",
                required=True,
            ),
            "regulatory_min_cet1": HelperParam(
                type="float",
                default=0.07,
                description=(
                    "CET1 regulatory minimum as decimal. Default 7.0% (Pillar 1 + conservation). "
                    "Pass higher for G-SIBs with surcharge (e.g. 0.09 for 9%)."
                ),
                required=False,
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
                name="banks_sector_panel_output",
                type="banks_sector_panel_output",
                description=(
                    "Full bank KPI panel: profitability (NIM, RoTCE, ROA, efficiency ratio, "
                    "fee income mix), capital adequacy (CET1, Tier 1, Total Capital, leverage, "
                    "buffer vs minimum), credit quality (NCO rate, NPL ratio, ACL coverage, "
                    "LLP build/release), liquidity (LDR, wholesale mix, deposit cost), "
                    "credit cycle phase, composite bank health score (0-100), warnings, "
                    "and narrative."
                ),
            ),
        ],
        produces_artifacts=["banks_sector_panel_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.praams_bank_income_statement", "eodhd.praams_bank_balance_sheet"],
    ),
    skill_doc=SkillDocRef(
        path="skills/banks_sector_panel.md",
        estimated_tokens=1800,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
