"""cost_of_capital_builder — cost of equity, cost of debt, and WACC.

Registered name: "cost_of_capital_builder"

Methods:
  "capm"     — re = rf + beta * ERP + lambda * CRP
  "hamada"   — relevering: beta_L = beta_U * [1 + (1-T) * D/E]
  "build_up" — re = rf + ERP + size_premium + specific_risk_premium
  "all"      — returns all three; primary method is capm

Design ref: planning/2026-05-22-helpers-design-supplement.md §2
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

_LOW_R2_THRESHOLD = 0.20  # below this, flag beta as low-confidence
_TV_PCT_HIGH_THRESHOLD = 0.75  # not used here but shared convention


# ---------------------------------------------------------------------------
# Core math — pure functions for testability
# ---------------------------------------------------------------------------


def _capm_cost_of_equity(
    rf: float,
    beta: float,
    erp: float,
    crp: float = 0.0,
    crp_lambda: float = 1.0,
) -> float:
    return rf + beta * erp + crp_lambda * crp


def _hamada_relever(beta_u: float, tax_rate: float, d_over_e: float) -> float:
    """beta_L = beta_U * [1 + (1-T) * D/E]."""
    return beta_u * (1.0 + (1.0 - tax_rate) * d_over_e)


def _hamada_unlever(beta_l: float, tax_rate: float, d_over_e: float) -> float:
    """beta_U = beta_L / [1 + (1-T) * D/E]."""
    return beta_l / (1.0 + (1.0 - tax_rate) * d_over_e)


def _build_up_cost_of_equity(
    rf: float,
    erp: float,
    size_premium: float = 0.0,
    specific_risk_premium: float = 0.0,
    crp: float = 0.0,
    crp_lambda: float = 1.0,
) -> float:
    return rf + erp + size_premium + specific_risk_premium + crp_lambda * crp


def _after_tax_cost_of_debt(pretax_rd: float, tax_rate: float) -> float:
    return pretax_rd * (1.0 - tax_rate)


def _wacc(
    cost_of_equity: float,
    after_tax_rd: float,
    equity_pct: float,
    debt_pct: float,
) -> float:
    return equity_pct * cost_of_equity + debt_pct * after_tax_rd


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    risk_free_rate: float,
    equity_risk_premium: float,
    marginal_tax_rate: float,
    pretax_cost_of_debt: float,
    equity_weight: float,
    debt_weight: float,
    method: str = "capm",
    beta: float | None = None,
    unlevered_beta: float | None = None,
    target_debt_to_equity: float | None = None,
    country_risk_premium: float = 0.0,
    country_risk_lambda: float = 1.0,
    size_premium: float = 0.0,
    specific_risk_premium: float = 0.0,
    beta_window_months: int | None = None,
    beta_r_squared: float | None = None,
    capital_structure_source: str = "current_market_values",
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Build cost of capital components and WACC.

    Args:
        risk_free_rate: 10-year Treasury yield (decimal, e.g. 0.043).
        equity_risk_premium: ERP in decimal form.
        marginal_tax_rate: Tax rate for after-tax cost of debt shield.
        pretax_cost_of_debt: Pre-tax cost of debt in decimal form.
        equity_weight: Equity as a fraction of total capital (E/V).
        debt_weight: Debt as a fraction of total capital (D/V).
        method: "capm" | "hamada" | "build_up" | "all".
        beta: Levered equity beta; required for capm and hamada.
        unlevered_beta: Industry/unlevered beta; required for hamada beta_source="industry".
        target_debt_to_equity: D/E for Hamada relevering; derived from weights if not provided.
        country_risk_premium: Damodaran CRP for EM exposure.
        country_risk_lambda: Exposure weight for CRP (1.0 = full domicile).
        size_premium: Ibbotson/Duff & Phelps size premium for build-up.
        specific_risk_premium: Company-specific risk premium for build-up.
        beta_window_months: Regression window months (for documentation).
        beta_r_squared: Regression R² (for documentation and low-R² flag).
        capital_structure_source: "current_market_values" | "target".
        data_as_of: ISO date for data freshness.
        source_provenance: List of citation IDs that fed this computation.
    """
    if method not in ("capm", "hamada", "build_up", "all"):
        raise ValueError(f"method must be capm|hamada|build_up|all, got {method!r}")

    # Normalise weights: must sum to 1.0 (within tolerance)
    total_w = equity_weight + debt_weight
    if abs(total_w - 1.0) > 0.001:
        raise ValueError(f"equity_weight + debt_weight must sum to 1.0, got {total_w:.4f}")

    warnings: list[str] = []

    # --- Beta / R² flags ---
    if beta_r_squared is not None and beta_r_squared < _LOW_R2_THRESHOLD:
        warnings.append(
            f"Regression beta R²={beta_r_squared:.2f} is below 0.20; "
            "industry beta + Hamada relevering recommended as an alternative."
        )

    # --- Derive D/E from weights when not provided ---
    if target_debt_to_equity is None:
        if equity_weight > 0:
            d_over_e = debt_weight / equity_weight
        else:
            d_over_e = float("inf")
    else:
        d_over_e = target_debt_to_equity

    # --- Check for negative equity ---
    if equity_weight <= 0:
        warnings.append(
            "Equity weight <= 0 (insolvent / negative equity). "
            "WACC is not meaningful; returning cost-of-equity from build-up only."
        )
        re_buildup = _build_up_cost_of_equity(
            risk_free_rate,
            equity_risk_premium,
            size_premium,
            specific_risk_premium,
            country_risk_premium,
            country_risk_lambda,
        )
        return {
            "method_used": "build_up_only_insolvent",
            "cost_of_equity": re_buildup,
            "wacc": None,
            "warnings": warnings,
            "data_as_of": data_as_of or datetime.date.today().isoformat(),
            "source_provenance": source_provenance or [],
        }

    after_tax_rd = _after_tax_cost_of_debt(pretax_cost_of_debt, marginal_tax_rate)

    def _build_result(re: float, method_name: str) -> dict[str, Any]:
        w = _wacc(re, after_tax_rd, equity_weight, debt_weight)
        return {
            "cost_of_equity": re,
            "wacc": w,
            "method": method_name,
        }

    # --- CAPM ---
    re_capm: float | None = None
    if beta is None and method in ("capm", "all"):
        warnings.append("beta is required for CAPM but was not provided; CAPM skipped.")
    else:
        if beta is not None:
            re_capm = _capm_cost_of_equity(
                risk_free_rate,
                beta,
                equity_risk_premium,
                country_risk_premium,
                country_risk_lambda,
            )

    # --- Hamada ---
    re_hamada: float | None = None
    relevered_beta: float | None = None
    if method in ("hamada", "all"):
        if unlevered_beta is not None:
            relevered_beta = _hamada_relever(unlevered_beta, marginal_tax_rate, d_over_e)
            re_hamada = _capm_cost_of_equity(
                risk_free_rate,
                relevered_beta,
                equity_risk_premium,
                country_risk_premium,
                country_risk_lambda,
            )
        elif beta is not None:
            # Unlever provided beta, then relever — net effect is same beta
            # but we expose the unlevered value for documentation
            beta_u = _hamada_unlever(beta, marginal_tax_rate, d_over_e)
            relevered_beta = _hamada_relever(beta_u, marginal_tax_rate, d_over_e)
            re_hamada = _capm_cost_of_equity(
                risk_free_rate,
                relevered_beta,
                equity_risk_premium,
                country_risk_premium,
                country_risk_lambda,
            )
            warnings.append(
                "Hamada: unlevered_beta not provided; used levered beta to derive "
                "unlevered then relevered. "
                "Provide unlevered_beta directly for more accurate results."
            )
        else:
            warnings.append("Hamada: neither beta nor unlevered_beta provided; Hamada skipped.")

    # --- Build-up ---
    re_buildup = _build_up_cost_of_equity(
        risk_free_rate,
        equity_risk_premium,
        size_premium,
        specific_risk_premium,
        country_risk_premium,
        country_risk_lambda,
    )

    # --- Assemble output ---
    primary_method = "capm" if method in ("capm", "all") else method
    if primary_method == "capm" and re_capm is None:
        primary_method = "build_up"  # fallback when beta unavailable

    primary_re: float
    if primary_method == "capm" and re_capm is not None:
        primary_re = re_capm
    elif primary_method == "hamada" and re_hamada is not None:
        primary_re = re_hamada
    else:
        primary_re = re_buildup
        primary_method = "build_up"

    primary_wacc = _wacc(primary_re, after_tax_rd, equity_weight, debt_weight)

    # Alternative methods (only populated when method == "all")
    alternative_methods: dict[str, Any] | None = None
    if method == "all":
        alternatives: dict[str, Any] = {}
        if re_hamada is not None:
            alternatives["hamada"] = _build_result(re_hamada, "hamada")
        alternatives["build_up"] = _build_result(re_buildup, "build_up")
        alternative_methods = alternatives if alternatives else None

    # Beta block for output
    beta_block: dict[str, Any] | None = None
    if beta is not None or relevered_beta is not None:
        beta_block = {
            "value": relevered_beta if relevered_beta is not None else beta,
            "unlevered_beta": (
                unlevered_beta
                if unlevered_beta is not None
                else (
                    _hamada_unlever(beta, marginal_tax_rate, d_over_e)
                    if beta is not None and d_over_e != float("inf")
                    else None
                )
            ),
            "relevered": relevered_beta is not None,
            "window_months": beta_window_months,
            "r_squared": beta_r_squared,
        }

    # Narrative
    narrative_parts: list[str] = []
    narrative_parts.append(f"{primary_method.upper()} cost of equity {primary_re * 100:.1f}%")
    if beta_block and beta_block.get("value") is not None:
        narrative_parts.append(f"beta {beta_block['value']:.2f}")
    if beta_r_squared is not None:
        narrative_parts.append(f"(R²={beta_r_squared:.2f})")
    narrative_parts.append(
        f"WACC {primary_wacc * 100:.1f}% at "
        f"{equity_weight * 100:.0f}/{debt_weight * 100:.0f} equity/debt split "
        f"with after-tax cost of debt {after_tax_rd * 100:.1f}%."
    )
    narrative = " ".join(narrative_parts)

    return {
        "method_used": primary_method,
        "risk_free_rate": risk_free_rate,
        "equity_risk_premium": equity_risk_premium,
        "country_risk_premium_applied": country_risk_premium * country_risk_lambda,
        "beta": beta_block,
        "cost_of_equity": primary_re,
        "pretax_cost_of_debt": pretax_cost_of_debt,
        "marginal_tax_rate": marginal_tax_rate,
        "after_tax_cost_of_debt": after_tax_rd,
        "capital_structure": {
            "equity_pct": equity_weight,
            "debt_pct": debt_weight,
            "source": capital_structure_source,
        },
        "wacc": primary_wacc,
        "alternative_methods": alternative_methods,
        "narrative": narrative,
        "warnings": warnings,
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
        name="cost_of_capital_builder",
        category=Category.DCF,
        one_liner=(
            "Build cost of equity (CAPM / Hamada / build-up), after-tax cost of debt, "
            "and WACC for any absolute valuation."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the discount rate (WACC) used by every absolute-valuation helper "
            "(DCF, DDM, SOTP, rNPV). Supports CAPM, Hamada relevering, and build-up methods. "
            "Exposes full decomposition so the drafter can cite each component."
        ),
        when_to_use=[
            "Before running dcf_engine, ddm_family, justified_multiples, or any helper that needs WACC.",  # noqa: E501
            "When updating the discount rate after a rate move or capital structure change.",
            "Sector reports comparing hurdle rates across peers.",
        ],
        when_not_to_use=[
            "Quick comparables-based valuation — WACC not required there.",
            "When ft_capital_structure already provides WACC and a simple cross-check suffices.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "risk_free_rate": HelperParam(
                type="float",
                description="10-year Treasury yield in decimal form (e.g. 0.043).",
                required=True,
            ),
            "equity_risk_premium": HelperParam(
                type="float",
                description="ERP in decimal form; use Damodaran current estimate.",
                required=True,
            ),
            "marginal_tax_rate": HelperParam(
                type="float",
                description="Marginal corporate tax rate; preferred over effective rate.",
                required=True,
            ),
            "pretax_cost_of_debt": HelperParam(
                type="float",
                description="Pre-tax cost of debt; from YTM or coupon/par schedule.",
                required=True,
            ),
            "equity_weight": HelperParam(
                type="float",
                description="E/V equity fraction. Must sum with debt_weight to 1.0.",
                required=True,
            ),
            "debt_weight": HelperParam(
                type="float",
                description="Debt as fraction of total capital (D/V).",
                required=True,
            ),
            "method": HelperParam(
                type="str",
                default="capm",
                description="capm | hamada | build_up | all.",
                required=False,
            ),
            "beta": HelperParam(
                type="float",
                default=None,
                description="Levered equity beta. Required for capm and hamada.",
                required=False,
            ),
            "unlevered_beta": HelperParam(
                type="float",
                default=None,
                description="Unlevered (asset) beta for Hamada relevering.",
                required=False,
            ),
            "target_debt_to_equity": HelperParam(
                type="float",
                default=None,
                description="D/E for Hamada; derived from weights if omitted.",
                required=False,
            ),
            "country_risk_premium": HelperParam(
                type="float",
                default=0.0,
                description="Damodaran CRP for EM exposure in decimal form.",
                required=False,
            ),
            "country_risk_lambda": HelperParam(
                type="float",
                default=1.0,
                description="CRP exposure weight; 1.0 = full domicile, lower for multinationals.",
                required=False,
            ),
            "size_premium": HelperParam(
                type="float",
                default=0.0,
                description="Build-up: Ibbotson/Duff & Phelps size decile premium.",
                required=False,
            ),
            "specific_risk_premium": HelperParam(
                type="float",
                default=0.0,
                description="Build-up: company-specific risk premium (private/distressed names).",
                required=False,
            ),
            "beta_window_months": HelperParam(
                type="int",
                default=60,
                description="Regression window in months (documentation only).",
                required=False,
            ),
            "beta_r_squared": HelperParam(
                type="float",
                default=None,
                description="Beta regression R²; below 0.20 triggers a low-confidence flag.",
                required=False,
            ),
            "capital_structure_source": HelperParam(
                type="str",
                default="current_market_values",
                description="current_market_values | target; recorded in output.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="cost_of_capital_output",
                type="cost_of_capital_output",
                description=(
                    "WACC, cost of equity, after-tax cost of debt, capital structure, "
                    "beta block, alternative methods when method=all, and narrative."
                ),
            ),
        ],
        produces_artifacts=["cost_of_capital_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.ust_yield_rates", "damodaran.erp"],
    ),
    skill_doc=SkillDocRef(
        path="skills/cost_of_capital_builder.md",
        estimated_tokens=2000,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
