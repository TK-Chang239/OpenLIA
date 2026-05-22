"""ft_cash_flow_metrics — FCF, FCFE, OCF margin, and cash flow quality via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.profitability_model as _prof
import financetoolkit.ratios.solvency_model as _solv

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
    operating_cash_flow: float,
    free_cash_flow: float,
    revenue: float,
    net_income: float,
    capital_expenditure: float = 0.0,
    interest_expense: float = 0.0,
    net_debt_repayment: float = 0.0,
    total_assets: float = 0.0,
    market_cap: float = 0.0,
) -> dict[str, Any]:
    """Compute cash flow quality and conversion metrics.

    FCFE = FCF - Net Debt Repayment (simplified; full FCFE requires equity issuance)
    OCF Margin = Operating Cash Flow / Revenue
    FCF Margin = Free Cash Flow / Revenue
    Cash Conversion = Operating Cash Flow / Net Income
    """
    if revenue == 0:
        raise ValueError("revenue must be non-zero")

    ocf_margin = operating_cash_flow / revenue
    fcf_margin = free_cash_flow / revenue if free_cash_flow != 0 else None

    # FCF to OCF ratio (quality indicator)
    fcf_to_ocf: float | None = None
    if operating_cash_flow != 0 and free_cash_flow != 0:
        fcf_to_ocf = float(
            _prof.get_free_cash_flow_operating_cash_flow_ratio(free_cash_flow, operating_cash_flow)
        )

    # Cash conversion (OCF quality vs. net income)
    income_quality: float | None = None
    if net_income != 0:
        income_quality = float(_prof.get_income_quality_ratio(operating_cash_flow, net_income))

    # FCF yield
    fcf_yield: float | None = None
    if free_cash_flow != 0 and market_cap != 0:
        fcf_yield = float(_solv.get_free_cash_flow_yield(free_cash_flow, market_cap))

    # FCFE (simplified: FCF minus net debt repayment)
    fcfe: float | None = None
    if free_cash_flow != 0:
        fcfe = free_cash_flow - net_debt_repayment

    # Capex coverage
    capex_coverage: float | None = None
    if capital_expenditure != 0 and operating_cash_flow != 0:
        capex_coverage = float(
            _solv.get_capex_coverage_ratio(operating_cash_flow, capital_expenditure)
        )

    # OCF to total assets (cash-based ROA)
    ocf_to_assets: float | None = None
    if total_assets != 0:
        ocf_to_assets = operating_cash_flow / total_assets

    return {
        "operating_cash_flow": operating_cash_flow,
        "free_cash_flow": free_cash_flow,
        "fcfe": fcfe,
        "ocf_margin": ocf_margin,
        "fcf_margin": fcf_margin,
        "fcf_to_ocf_ratio": fcf_to_ocf,
        "income_quality_ratio": income_quality,
        "fcf_yield": fcf_yield,
        "capex_coverage": capex_coverage,
        "ocf_to_total_assets": ocf_to_assets,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_cash_flow_metrics",
        category=Category.BUSINESS_QUALITY,
        one_liner="OCF margin, FCF margin, cash conversion quality, and FCFE.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute cash flow quality metrics — OCF margin, FCF margin, income quality, "
            "FCF yield, and FCFE — from cash flow statement and income statement scalars."
        ),
        when_to_use=[
            "Assessing cash generation quality in an equity research report.",
            "Checking whether reported earnings are backed by operating cash flow.",
        ],
        when_not_to_use=[
            "Per-share cash flow metrics — use ft_per_share_metrics.",
            "Dividend metrics — use ft_dividend_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "operating_cash_flow": HelperParam(
                type="float", required=True, description="Net cash from operations."
            ),
            "free_cash_flow": HelperParam(
                type="float", required=True, description="Free cash flow (OCF - capex)."
            ),
            "revenue": HelperParam(type="float", required=True, description="Total revenue."),
            "net_income": HelperParam(type="float", required=True, description="Net income."),
            "capital_expenditure": HelperParam(
                type="float", required=False, default=0.0, description="Capital expenditure."
            ),
            "interest_expense": HelperParam(
                type="float", required=False, default=0.0, description="Interest expense."
            ),
            "net_debt_repayment": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net debt repayment (positive = reducing debt).",
            ),
            "total_assets": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Total assets for OCF/assets ratio.",
            ),
            "market_cap": HelperParam(
                type="float", required=False, default=0.0, description="Market cap for FCF yield."
            ),
        },
        outputs=[
            HelperOutput(
                name="cash_flow_metrics",
                type="dict",
                description=(
                    "Dict with operating_cash_flow, free_cash_flow, fcfe, ocf_margin, "
                    "fcf_margin, fcf_to_ocf_ratio, income_quality_ratio, fcf_yield, "
                    "capex_coverage, ocf_to_total_assets."
                ),
            ),
        ],
        produces_artifacts=["ft_cash_flow_metrics_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
