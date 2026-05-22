"""ft_quality_metrics — accruals, earnings quality, and financial sustainability indicators."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.profitability_model as _prof

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
    net_income: float,
    operating_cash_flow: float,
    total_assets: float,
    revenue: float,
    free_cash_flow: float = 0.0,
    ebit: float = 0.0,
    depreciation_and_amortization: float = 0.0,
    total_assets_prior: float = 0.0,
    net_income_prior: float = 0.0,
    total_debt: float = 0.0,
    total_equity: float = 0.0,
    capex: float = 0.0,
    shares_outstanding: float = 0.0,
    shares_outstanding_prior: float = 0.0,
) -> dict[str, Any]:
    """Compute earnings quality and financial sustainability indicators.

    Sloan Accrual Ratio = (Net Income - Operating CF) / Avg Total Assets
    A high accrual ratio signals earnings are outpacing cash flow (lower quality).

    Income Quality Ratio (FinanceToolkit) = Operating CF / Net Income
    A ratio > 1 signals cash-backed earnings.

    Sustainability Index = FCF / Net Income
    A ratio > 1 signals earnings are fully backed by free cash flow.
    """
    if total_assets == 0:
        raise ValueError("total_assets must be non-zero")

    # Accrual ratio (Sloan 1996): positive = accrual-heavy earnings
    avg_assets = (
        (total_assets + total_assets_prior) / 2 if total_assets_prior != 0 else total_assets
    )
    accrual_ratio = (net_income - operating_cash_flow) / avg_assets

    # FinanceToolkit income quality = OCF / NI
    income_quality: float | None = None
    if net_income != 0:
        income_quality = float(_prof.get_income_quality_ratio(operating_cash_flow, net_income))

    # FCF/NI sustainability
    fcf_to_ni: float | None = None
    if free_cash_flow != 0 and net_income != 0:
        fcf_to_ni = free_cash_flow / net_income

    # OCF margin (cash earnings quality vs. revenue)
    ocf_margin = operating_cash_flow / revenue if revenue != 0 else None

    # ROA trend (positive = improving profitability)
    roa = net_income / total_assets
    roa_prior: float | None = None
    roa_improving: bool | None = None
    if total_assets_prior != 0 and net_income_prior != 0:
        roa_prior = net_income_prior / total_assets_prior
        roa_improving = roa > roa_prior

    # Capex intensity (CapEx / Revenue) — high intensity may constrain FCF
    capex_intensity: float | None = None
    if capex != 0 and revenue != 0:
        capex_intensity = capex / revenue

    # Reinvestment rate = CapEx / Operating CF (how much of OCF goes to reinvestment)
    reinvestment_rate: float | None = None
    if capex != 0 and operating_cash_flow != 0:
        reinvestment_rate = capex / operating_cash_flow

    # Dilution signal: shares growing = negative quality signal
    dilution_signal: bool | None = None
    if shares_outstanding != 0 and shares_outstanding_prior != 0:
        dilution_signal = shares_outstanding > shares_outstanding_prior

    return {
        "accrual_ratio": round(accrual_ratio, 4),
        "income_quality_ratio": income_quality,
        "fcf_to_net_income": fcf_to_ni,
        "ocf_margin": ocf_margin,
        "roa": round(roa, 4),
        "roa_prior": round(roa_prior, 4) if roa_prior is not None else None,
        "roa_improving": roa_improving,
        "capex_intensity": capex_intensity,
        "reinvestment_rate": reinvestment_rate,
        "shares_diluting": dilution_signal,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_quality_metrics",
        category=Category.BUSINESS_QUALITY,
        one_liner="Accruals, earnings quality, OCF coverage, and sustainability indicators.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute earnings quality signals — accrual ratio, income quality, FCF/NI "
            "sustainability, and dilution — from financial statement scalars."
        ),
        when_to_use=[
            "Red-flag screening for low-quality earnings in an equity research report.",
            "Supplementing Piotroski F-Score with accrual and dilution analysis.",
        ],
        when_not_to_use=[
            "Full Piotroski F-Score — use ft_piotroski_f_score.",
            "SaaS-specific quality metrics (NRR, churn) — use saas_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(type="float", required=True, description="Net income."),
            "operating_cash_flow": HelperParam(
                type="float", required=True, description="Operating cash flow."
            ),
            "total_assets": HelperParam(type="float", required=True, description="Total assets."),
            "revenue": HelperParam(type="float", required=True, description="Total revenue."),
            "free_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="FCF for sustainability ratio.",
            ),
            "ebit": HelperParam(type="float", required=False, default=0.0, description="EBIT."),
            "depreciation_and_amortization": HelperParam(
                type="float", required=False, default=0.0, description="D&A."
            ),
            "total_assets_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Prior period total assets for Sloan accrual avg and ROA trend.",
            ),
            "net_income_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Prior period net income for ROA trend.",
            ),
            "total_debt": HelperParam(
                type="float", required=False, default=0.0, description="Total debt."
            ),
            "total_equity": HelperParam(
                type="float", required=False, default=0.0, description="Total equity."
            ),
            "capex": HelperParam(
                type="float", required=False, default=0.0, description="Capital expenditure."
            ),
            "shares_outstanding": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Current period shares outstanding.",
            ),
            "shares_outstanding_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Prior period shares outstanding.",
            ),
        },
        outputs=[
            HelperOutput(
                name="quality_metrics",
                type="dict",
                description=(
                    "Dict with accrual_ratio, income_quality_ratio, fcf_to_net_income, "
                    "ocf_margin, roa, roa_prior, roa_improving, capex_intensity, "
                    "reinvestment_rate, shares_diluting."
                ),
            ),
        ],
        produces_artifacts=["ft_quality_metrics_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
