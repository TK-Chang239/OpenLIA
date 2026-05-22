"""saas_kpi_panel — quarterly SaaS KPI synthesis panel.

Registered name: "saas_kpi_panel"
Category: SAAS_KPIS

Supersedes saas_metrics (deprecated at PR 2.9). Computes the full set of
investor-facing SaaS KPIs from disclosed quarterly metrics:

  ARR, NRR, GRR, implied churn, Magic Number, RPO, Billings, CAC payback,
  LTV/CAC, customer concentration, Rule of 40, composite health score.

Magic Number formula (audit fix §9 / design §6.1):
  Magic_Number = net_new_ARR_this_quarter / sm_spend_prior_quarter
  NO x4 annualization — ARR is already an annualized figure.
  net_new_ARR = arr_current - arr_prior_quarter (sequential delta).

Design ref: planning/2026-05-21-equity-research-helpers-design.md §6.1 + §9
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
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _rule_of_40_class(value: float) -> str:
    if value >= 50:
        return "excellent"
    if value >= 40:
        return "healthy"
    if value >= 30:
        return "acceptable"
    return "weak"


def _nrr_class(value: float) -> str:
    if value > 1.20:
        return "best_in_class"
    if value >= 1.10:
        return "strong"
    if value >= 1.00:
        return "stable"
    return "shrinking"


def _grr_class(value: float) -> str:
    if value > 0.95:
        return "strong"
    if value >= 0.90:
        return "moderate"
    return "weak"


def _magic_number_class(value: float) -> str:
    if value > 1.0:
        return "efficient"
    if value >= 0.5:
        return "moderate"
    return "inefficient"


def _ltv_cac_class(value: float) -> str:
    if value > 3.0:
        return "healthy"
    if value >= 1.5:
        return "moderate"
    return "weak"


def _cac_payback_class(months: float) -> str:
    if months <= 12:
        return "strong"
    if months <= 24:
        return "moderate"
    return "long"


# ---------------------------------------------------------------------------
# Composite health score
# ---------------------------------------------------------------------------

_HEALTH_SCORE_WEIGHTS: dict[str, float] = {
    "rule_of_40": 0.25,
    "nrr": 0.25,
    "magic_number": 0.20,
    "ltv_cac": 0.15,
    "grr": 0.15,
}

_SCORE_MAP: dict[str, float] = {
    # rule_of_40
    "excellent": 1.0,
    "healthy": 0.75,
    "acceptable": 0.50,
    "weak": 0.25,
    # nrr
    "best_in_class": 1.0,
    "strong": 0.75,
    "stable": 0.50,
    "shrinking": 0.0,
    # magic_number
    "efficient": 1.0,
    "moderate": 0.50,
    "inefficient": 0.0,
    # ltv_cac
    # "healthy" / "moderate" / "weak" already mapped
    # grr
    # "strong" / "moderate" / "weak" already mapped
    # cac_payback (not in composite)
    "long": 0.25,
}


def _component_score(classification: str) -> float:
    return _SCORE_MAP.get(classification, 0.50)


def _compute_health_score(
    rule_of_40_class: str | None,
    nrr_class: str | None,
    magic_number_class: str | None,
    ltv_cac_class: str | None,
    grr_class: str | None,
) -> float | None:
    """Weighted composite score in [0, 1]. Returns None if no component available."""
    classes = {
        "rule_of_40": rule_of_40_class,
        "nrr": nrr_class,
        "magic_number": magic_number_class,
        "ltv_cac": ltv_cac_class,
        "grr": grr_class,
    }
    available = {k: v for k, v in classes.items() if v is not None}
    if not available:
        return None
    total_weight = sum(_HEALTH_SCORE_WEIGHTS[k] for k in available)
    score = sum(
        _component_score(cls) * _HEALTH_SCORE_WEIGHTS[k] / total_weight
        for k, cls in available.items()
    )
    return round(score, 4)


def _health_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.80:
        return "strong"
    if score >= 0.60:
        return "healthy"
    if score >= 0.40:
        return "mixed"
    return "weak"


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    arr_current: float,
    arr_prior_year: float | None = None,
    arr_prior_quarter: float | None = None,
    revenue_growth_rate: float | None = None,
    fcf_margin: float | None = None,
    nrr: float | None = None,
    grr: float | None = None,
    new_arr_this_quarter: float | None = None,
    sm_spend_prior_quarter: float | None = None,
    rpo: float | None = None,
    revenue_current_period: float | None = None,
    deferred_revenue_current: float | None = None,
    deferred_revenue_prior: float | None = None,
    ltv: float | None = None,
    cac: float | None = None,
    cac_payback_months: float | None = None,
    gross_margin: float | None = None,
    customer_count_current: int | None = None,
    customer_count_prior_year: int | None = None,
    top_10_customer_revenue_pct: float | None = None,
    as_of: str | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute the quarterly SaaS KPI panel.

    Args:
        arr_current: Current ARR (required). Annualized recurring revenue.
        arr_prior_year: ARR from same quarter prior year, for YoY growth.
        arr_prior_quarter: ARR from prior quarter, for QoQ growth + Magic Number.
        revenue_growth_rate: YoY revenue growth rate as decimal (for Rule of 40).
        fcf_margin: Free cash flow margin as decimal (for Rule of 40).
        nrr: Net revenue retention as decimal (e.g. 1.18 for 118%).
        grr: Gross revenue retention as decimal (e.g. 0.95 for 95%).
        new_arr_this_quarter: Net new ARR added this quarter (optional override
            for Magic Number numerator; if omitted, derived from arr_current -
            arr_prior_quarter when arr_prior_quarter is provided).
        sm_spend_prior_quarter: S&M expense in the prior quarter (Magic Number denominator).
        rpo: Remaining performance obligation (backlog). Pass-through.
        revenue_current_period: Current period revenue (for Billings calculation).
        deferred_revenue_current: Deferred revenue at end of current period.
        deferred_revenue_prior: Deferred revenue at end of prior period.
        ltv: Customer lifetime value.
        cac: Customer acquisition cost.
        cac_payback_months: CAC payback period in months (if pre-calculated).
        gross_margin: Gross margin as decimal (used for CAC payback when not disclosed).
        customer_count_current: Current customer count.
        customer_count_prior_year: Customer count from same quarter prior year.
        top_10_customer_revenue_pct: Top 10 customers as % of revenue (decimal).
        as_of: Quarter label, e.g. "2026-Q1".
        data_as_of: ISO date for data freshness.
        source_provenance: Upstream citation IDs.

    Returns:
        Dict of all metrics, composite health score, disclosure completeness,
        warnings, and narrative summary.
    """
    warnings: list[str] = []
    disclosed_count = 0
    total_metrics = 0

    def _metric(
        value: Any,
        disclosed: bool,
        **fields: Any,
    ) -> dict[str, Any]:
        nonlocal disclosed_count, total_metrics
        total_metrics += 1
        if disclosed:
            disclosed_count += 1
        return {"value": value, "disclosed": disclosed, **fields}

    # ------------------------------------------------------------------
    # ARR
    # ------------------------------------------------------------------
    yoy_growth_pct: float | None = None
    qoq_growth_pct: float | None = None

    if arr_prior_year is not None and arr_prior_year > 0:
        yoy_growth_pct = round((arr_current - arr_prior_year) / arr_prior_year, 6)
    if arr_prior_quarter is not None and arr_prior_quarter > 0:
        qoq_growth_pct = round((arr_current - arr_prior_quarter) / arr_prior_quarter, 6)

    arr_block = {
        "current": arr_current,
        "yoy_growth_pct": yoy_growth_pct,
        "qoq_growth_pct": qoq_growth_pct,
        "disclosed": True,
    }
    disclosed_count += 1
    total_metrics += 1

    # ------------------------------------------------------------------
    # NRR
    # ------------------------------------------------------------------
    nrr_block: dict[str, Any] | None = None
    nrr_cls: str | None = None
    if nrr is not None:
        nrr_cls = _nrr_class(nrr)
        nrr_block = _metric(
            nrr,
            disclosed=True,
            classification=nrr_cls,
            threshold_healthy=1.10,
        )
    else:
        total_metrics += 1  # counts as missing

    # ------------------------------------------------------------------
    # GRR + implied churn
    # ------------------------------------------------------------------
    grr_block: dict[str, Any] | None = None
    implied_churn_block: dict[str, Any] | None = None
    grr_cls: str | None = None
    if grr is not None:
        grr_cls = _grr_class(grr)
        grr_block = _metric(
            grr,
            disclosed=True,
            classification=grr_cls,
            threshold_healthy=0.90,
        )
        implied_churn_val = round(1.0 - grr, 6)
        implied_churn_block = {
            "value": implied_churn_val,
            "calculation": "1 - GRR",
            "disclosed": False,
        }
    else:
        total_metrics += 1  # GRR missing

    # ------------------------------------------------------------------
    # Magic Number  (audit-fix §9: no x4)
    # ------------------------------------------------------------------
    magic_block: dict[str, Any] | None = None
    magic_cls: str | None = None
    net_new_arr: float | None = None

    if new_arr_this_quarter is not None:
        net_new_arr = new_arr_this_quarter
    elif arr_prior_quarter is not None:
        net_new_arr = arr_current - arr_prior_quarter

    if net_new_arr is not None and sm_spend_prior_quarter is not None:
        if sm_spend_prior_quarter <= 0:
            warnings.append("sm_spend_prior_quarter must be positive to compute Magic Number.")
        else:
            magic_val = round(net_new_arr / sm_spend_prior_quarter, 6)
            magic_cls = _magic_number_class(magic_val)
            magic_block = _metric(
                magic_val,
                disclosed=False,
                classification=magic_cls,
                calculation=(
                    "net_new_ARR_this_quarter / S&M_prior_quarter "
                    "(no x4 — ARR is already annualized)"
                ),
            )
    else:
        total_metrics += 1  # Magic Number missing

    # ------------------------------------------------------------------
    # RPO
    # ------------------------------------------------------------------
    rpo_block: dict[str, Any] | None = None
    if rpo is not None:
        rpo_block = _metric(rpo, disclosed=True)
    else:
        total_metrics += 1

    # ------------------------------------------------------------------
    # Billings = Revenue + ΔDeferred Revenue
    # ------------------------------------------------------------------
    billings_block: dict[str, Any] | None = None
    if (
        revenue_current_period is not None
        and deferred_revenue_current is not None
        and deferred_revenue_prior is not None
    ):
        billings_val = round(
            revenue_current_period + (deferred_revenue_current - deferred_revenue_prior),
            2,
        )
        billings_block = {
            "value": billings_val,
            "calculation": "revenue + delta_deferred_revenue",
            "disclosed": False,
        }
        total_metrics += 1
    else:
        total_metrics += 1

    # ------------------------------------------------------------------
    # CAC payback period (months)
    # ------------------------------------------------------------------
    cac_payback_block: dict[str, Any] | None = None
    cac_payback_cls: str | None = None
    effective_payback: float | None = None

    if cac_payback_months is not None:
        effective_payback = cac_payback_months
        cac_payback_cls = _cac_payback_class(effective_payback)
        cac_payback_block = _metric(
            effective_payback,
            disclosed=True,
            classification=cac_payback_cls,
        )
    elif cac is not None and gross_margin is not None and gross_margin > 0:
        # Derive ARPA from ARR / customer_count if customer_count available
        if customer_count_current and customer_count_current > 0:
            arpa_monthly = (arr_current / customer_count_current) / 12.0
            gm_arpa = arpa_monthly * gross_margin
            if gm_arpa > 0:
                effective_payback = round(cac / gm_arpa, 2)
                cac_payback_cls = _cac_payback_class(effective_payback)
                cac_payback_block = {
                    "value": effective_payback,
                    "calculation": "CAC / (ARPA_monthly * gross_margin)",
                    "disclosed": False,
                    "classification": cac_payback_cls,
                }
                total_metrics += 1
            else:
                total_metrics += 1
        else:
            total_metrics += 1
    else:
        total_metrics += 1

    # ------------------------------------------------------------------
    # LTV / CAC
    # ------------------------------------------------------------------
    ltv_cac_block: dict[str, Any] | None = None
    ltv_cac_cls: str | None = None

    if ltv is not None and cac is not None and cac > 0:
        ltv_cac_val = round(ltv / cac, 4)
        ltv_cac_cls = _ltv_cac_class(ltv_cac_val)
        ltv_cac_block = _metric(
            ltv_cac_val,
            disclosed=True,
            classification=ltv_cac_cls,
            threshold_healthy=3.0,
        )
    else:
        total_metrics += 1

    # ------------------------------------------------------------------
    # Customer concentration
    # ------------------------------------------------------------------
    concentration_block: dict[str, Any] | None = None
    if top_10_customer_revenue_pct is not None:
        concentration_block = _metric(
            top_10_customer_revenue_pct,
            disclosed=True,
            description="top_10_customers_pct_of_revenue",
        )
        if top_10_customer_revenue_pct > 0.30:
            warnings.append(
                f"Top 10 customers represent {top_10_customer_revenue_pct:.1%} of revenue — "
                "elevated concentration risk."
            )
    else:
        total_metrics += 1

    # ------------------------------------------------------------------
    # Customer count
    # ------------------------------------------------------------------
    customer_count_block: dict[str, Any] | None = None
    if customer_count_current is not None:
        cc_yoy: float | None = None
        if customer_count_prior_year is not None and customer_count_prior_year > 0:
            cc_yoy = round(
                (customer_count_current - customer_count_prior_year) / customer_count_prior_year,
                6,
            )
        customer_count_block = {
            "current": customer_count_current,
            "yoy_growth_pct": cc_yoy,
            "disclosed": True,
        }
        disclosed_count += 1
        total_metrics += 1
    else:
        total_metrics += 1

    # ------------------------------------------------------------------
    # Rule of 40
    # ------------------------------------------------------------------
    rule_of_40_block: dict[str, Any] | None = None
    ro40_cls: str | None = None

    if revenue_growth_rate is not None and fcf_margin is not None:
        ro40_val = round(revenue_growth_rate * 100 + fcf_margin * 100, 4)
        ro40_cls = _rule_of_40_class(ro40_val)
        rule_of_40_block = _metric(
            ro40_val,
            disclosed=True,
            components={
                "revenue_growth_pct": round(revenue_growth_rate * 100, 4),
                "fcf_margin_pct": round(fcf_margin * 100, 4),
            },
            classification=ro40_cls,
            threshold=40,
        )
    else:
        total_metrics += 1
        if revenue_growth_rate is None and fcf_margin is not None:
            warnings.append("revenue_growth_rate missing — Rule of 40 not computed.")
        elif fcf_margin is None and revenue_growth_rate is not None:
            warnings.append("fcf_margin missing — Rule of 40 not computed.")

    # ------------------------------------------------------------------
    # Composite health score
    # ------------------------------------------------------------------
    health_score = _compute_health_score(ro40_cls, nrr_cls, magic_cls, ltv_cac_cls, grr_cls)
    health_label = _health_label(health_score)

    # ------------------------------------------------------------------
    # Disclosure completeness
    # ------------------------------------------------------------------
    disclosure_completeness = (
        round(disclosed_count / total_metrics, 4) if total_metrics > 0 else 0.0
    )

    # ------------------------------------------------------------------
    # Narrative
    # ------------------------------------------------------------------
    parts: list[str] = []
    if yoy_growth_pct is not None:
        parts.append(f"ARR YoY +{yoy_growth_pct:.1%}")
    if nrr is not None:
        parts.append(f"NRR {nrr:.0%}")
    if grr is not None:
        parts.append(f"GRR {grr:.0%}")
    if magic_block is not None:
        parts.append(f"Magic Number {magic_block['value']:.2f} ({magic_cls})")
    if rule_of_40_block is not None:
        parts.append(f"Rule of 40: {rule_of_40_block['value']:.1f} ({ro40_cls})")
    if ltv_cac_block is not None:
        parts.append(f"LTV/CAC {ltv_cac_block['value']:.1f}x")
    narrative = "; ".join(parts) if parts else "Insufficient data for narrative."
    if health_label:
        narrative += f". Overall SaaS health: {health_label}."

    return {
        "as_of": as_of or datetime.date.today().strftime("%Y-Q?"),
        "arr": arr_block,
        "nrr": nrr_block,
        "grr": grr_block,
        "implied_churn_rate": implied_churn_block,
        "magic_number": magic_block,
        "rpo": rpo_block,
        "billings": billings_block,
        "cac_payback_months": cac_payback_block,
        "ltv_cac": ltv_cac_block,
        "customer_concentration": concentration_block,
        "customer_count": customer_count_block,
        "rule_of_40": rule_of_40_block,
        "composite_health_score": {
            "value": health_score,
            "label": health_label,
            "components_used": [
                k
                for k, v in {
                    "rule_of_40": ro40_cls,
                    "nrr": nrr_cls,
                    "magic_number": magic_cls,
                    "ltv_cac": ltv_cac_cls,
                    "grr": grr_cls,
                }.items()
                if v is not None
            ],
        },
        "disclosure_completeness": disclosure_completeness,
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
        name="saas_kpi_panel",
        category=Category.SAAS_KPIS,
        one_liner=(
            "Quarterly SaaS KPI panel: ARR, NRR, GRR, Magic Number, Rule of 40, "
            "LTV/CAC, Billings, RPO, health score."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Synthesize all investor-facing SaaS KPIs from disclosed quarterly metrics "
            "into a single structured panel with classifications, thresholds, and a "
            "composite SaaS health score."
        ),
        when_to_use=[
            "Analyzing a SaaS company's quarterly KPI health across retention, growth, "
            "and unit economics.",
            "Computing Magic Number (S&M efficiency), Rule of 40, or LTV/CAC from "
            "partially-disclosed metrics.",
            "Building a SaaS tearsheet section that requires disclosure completeness tracking.",
        ],
        when_not_to_use=[
            "Non-SaaS businesses — use ratio_calculator or ft_profitability_ratios.",
            "Full DCF valuation — use dcf_valuation.",
            "MRR-level simulation or quick-ratio decomposition — use saas_metrics "
            "(note: deprecated; pending removal).",
        ],
    ),
    contract=MechanicalContract(
        params={
            "arr_current": HelperParam(
                type="float",
                description="Current ARR (annualized recurring revenue).",
                required=True,
            ),
            "arr_prior_year": HelperParam(
                type="float",
                default=None,
                description="ARR from same quarter prior year, for YoY growth.",
                required=False,
            ),
            "arr_prior_quarter": HelperParam(
                type="float",
                default=None,
                description=(
                    "ARR from prior quarter. Used for QoQ growth and as Magic Number "
                    "numerator fallback when new_arr_this_quarter is not provided."
                ),
                required=False,
            ),
            "revenue_growth_rate": HelperParam(
                type="float",
                default=None,
                description="YoY revenue growth rate as decimal (for Rule of 40).",
                required=False,
            ),
            "fcf_margin": HelperParam(
                type="float",
                default=None,
                description="Free cash flow margin as decimal (for Rule of 40).",
                required=False,
            ),
            "nrr": HelperParam(
                type="float",
                default=None,
                description="Net revenue retention as decimal (e.g. 1.18 for 118%).",
                required=False,
            ),
            "grr": HelperParam(
                type="float",
                default=None,
                description="Gross revenue retention as decimal (e.g. 0.95 for 95%).",
                required=False,
            ),
            "new_arr_this_quarter": HelperParam(
                type="float",
                default=None,
                description=(
                    "Net new ARR added this quarter (Magic Number numerator). "
                    "If omitted, derived as arr_current - arr_prior_quarter."
                ),
                required=False,
            ),
            "sm_spend_prior_quarter": HelperParam(
                type="float",
                default=None,
                description="S&M expense in the prior quarter (Magic Number denominator).",
                required=False,
            ),
            "rpo": HelperParam(
                type="float",
                default=None,
                description="Remaining performance obligation.",
                required=False,
            ),
            "revenue_current_period": HelperParam(
                type="float",
                default=None,
                description="Current period revenue (for Billings = Revenue + ΔDeferred).",
                required=False,
            ),
            "deferred_revenue_current": HelperParam(
                type="float",
                default=None,
                description="Deferred revenue at end of current period.",
                required=False,
            ),
            "deferred_revenue_prior": HelperParam(
                type="float",
                default=None,
                description="Deferred revenue at end of prior period.",
                required=False,
            ),
            "ltv": HelperParam(
                type="float",
                default=None,
                description="Customer lifetime value.",
                required=False,
            ),
            "cac": HelperParam(
                type="float",
                default=None,
                description="Customer acquisition cost.",
                required=False,
            ),
            "cac_payback_months": HelperParam(
                type="float",
                default=None,
                description="CAC payback period in months (if pre-calculated).",
                required=False,
            ),
            "gross_margin": HelperParam(
                type="float",
                default=None,
                description=(
                    "Gross margin as decimal. Used to derive CAC payback "
                    "when cac_payback_months is not disclosed."
                ),
                required=False,
            ),
            "customer_count_current": HelperParam(
                type="int",
                default=None,
                description="Current customer count.",
                required=False,
            ),
            "customer_count_prior_year": HelperParam(
                type="int",
                default=None,
                description="Customer count from same quarter prior year.",
                required=False,
            ),
            "top_10_customer_revenue_pct": HelperParam(
                type="float",
                default=None,
                description=("Top 10 customers as fraction of total revenue (decimal, e.g. 0.25)."),
                required=False,
            ),
            "as_of": HelperParam(
                type="str",
                default=None,
                description='Quarter label, e.g. "2026-Q1".',
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="saas_kpi_panel_output",
                type="saas_kpi_panel_output",
                description=(
                    "Full SaaS KPI panel: ARR growth, NRR, GRR, implied churn, "
                    "Magic Number, RPO, Billings, CAC payback, LTV/CAC, customer "
                    "concentration, Rule of 40, composite health score, disclosure "
                    "completeness, warnings, and narrative."
                ),
            ),
        ],
        produces_artifacts=["saas_kpi_panel_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,  # not on the 18-complex list per schema-and-skills §6
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
