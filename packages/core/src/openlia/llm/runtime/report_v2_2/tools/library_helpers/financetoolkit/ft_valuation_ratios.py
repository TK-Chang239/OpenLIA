"""ft_valuation_ratios — P/E, P/B, EV/EBITDA from price and financials via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.valuation_model as _val

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
    share_price: float,
    shares_outstanding: float,
    net_income: float,
    total_equity: float,
    revenue: float,
    operating_income: float,
    depreciation_and_amortization: float = 0.0,
    total_debt: float = 0.0,
    cash_and_equivalents: float = 0.0,
    minority_interest: float = 0.0,
    preferred_equity: float = 0.0,
    free_cash_flow: float = 0.0,
    operating_cash_flow: float = 0.0,
    dividends_per_share: float = 0.0,
    eps_growth_rate: float = 0.0,
    preferred_dividends: float = 0.0,
) -> dict[str, Any]:
    """Compute valuation ratios from price and financial statement inputs."""
    market_cap = float(_val.get_market_cap(share_price, shares_outstanding))

    eps = float(_val.get_earnings_per_share(net_income, preferred_dividends, shares_outstanding))

    bvps = float(_val.get_book_value_per_share(total_equity, preferred_equity, shares_outstanding))

    pe_ratio: float | None = None
    if eps != 0:
        pe_ratio = float(_val.get_price_to_earnings_ratio(share_price, eps))

    pb_ratio: float | None = None
    if bvps != 0:
        pb_ratio = float(_val.get_price_to_book_ratio(share_price, bvps))

    ev = float(
        _val.get_enterprise_value(
            market_cap, total_debt, minority_interest, preferred_equity, cash_and_equivalents
        )
    )

    ebitda = operating_income + depreciation_and_amortization
    ev_to_ebitda: float | None = None
    if ebitda != 0:
        ev_to_ebitda = float(
            _val.get_ev_to_ebitda_ratio(ev, operating_income, depreciation_and_amortization)
        )

    ev_to_ebit: float | None = None
    if operating_income != 0:
        ev_to_ebit = float(_val.get_ev_to_ebit(ev, operating_income))

    ev_to_sales: float | None = None
    if revenue != 0:
        ev_to_sales = float(_val.get_ev_to_sales_ratio(ev, revenue))

    revenue_per_share = float(_val.get_revenue_per_share(revenue, shares_outstanding))

    ps_ratio: float | None = None
    if revenue_per_share != 0:
        ps_ratio = share_price / revenue_per_share

    pcf_ratio: float | None = None
    if operating_cash_flow != 0:
        pcf_ratio = float(_val.get_price_to_cash_flow_ratio(market_cap, operating_cash_flow))

    pfcf_ratio: float | None = None
    if free_cash_flow != 0:
        pfcf_ratio = float(_val.get_price_to_free_cash_flow_ratio(market_cap, free_cash_flow))

    dividend_yield: float | None = None
    if dividends_per_share != 0 and share_price != 0:
        dividend_yield = float(_val.get_dividend_yield(dividends_per_share, share_price))

    peg_ratio: float | None = None
    if pe_ratio is not None and eps_growth_rate != 0:
        peg_ratio = float(
            _val.get_price_to_earnings_growth_ratio(share_price, eps, eps_growth_rate)
        )

    return {
        "market_cap": market_cap,
        "enterprise_value": ev,
        "eps": eps,
        "book_value_per_share": bvps,
        "revenue_per_share": revenue_per_share,
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
        "ps_ratio": ps_ratio,
        "ev_to_ebitda": ev_to_ebitda,
        "ev_to_ebit": ev_to_ebit,
        "ev_to_sales": ev_to_sales,
        "price_to_cash_flow": pcf_ratio,
        "price_to_free_cash_flow": pfcf_ratio,
        "dividend_yield": dividend_yield,
        "peg_ratio": peg_ratio,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_valuation_ratios",
        category=Category.BUSINESS_QUALITY,
        one_liner="P/E, P/B, EV/EBITDA, and market multiples from price + financials.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute market valuation multiples using FinanceToolkit model functions "
            "applied to user-supplied price, share count, and financial statement scalars."
        ),
        when_to_use=[
            "Computing market multiples for a valuation section in an equity research report.",
            "Peer multiple comparison requiring EV/EBITDA, P/E, P/B, EV/Sales.",
        ],
        when_not_to_use=[
            "Full DCF intrinsic valuation — use dcf_valuation.",
            "Per-share operating metrics — use ft_per_share_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "share_price": HelperParam(
                type="float",
                required=True,
                description="Current share price.",
            ),
            "shares_outstanding": HelperParam(
                type="float",
                required=True,
                description="Diluted shares outstanding.",
            ),
            "net_income": HelperParam(
                type="float",
                required=True,
                description="Net income.",
            ),
            "total_equity": HelperParam(
                type="float",
                required=True,
                description="Total shareholder equity.",
            ),
            "revenue": HelperParam(
                type="float",
                required=True,
                description="Total revenue.",
            ),
            "operating_income": HelperParam(
                type="float",
                required=True,
                description="Operating income (EBIT).",
            ),
            "depreciation_and_amortization": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="D&A for EBITDA calculation.",
            ),
            "total_debt": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Total debt for EV calculation.",
            ),
            "cash_and_equivalents": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Cash for EV calculation.",
            ),
            "minority_interest": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Minority interest for EV calculation.",
            ),
            "preferred_equity": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Preferred equity for EV and BVPS calculations.",
            ),
            "free_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Free cash flow for P/FCF ratio.",
            ),
            "operating_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Operating cash flow for P/CF ratio.",
            ),
            "dividends_per_share": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Annual dividends per share for dividend yield.",
            ),
            "eps_growth_rate": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="EPS growth rate (decimal) for PEG ratio.",
            ),
            "preferred_dividends": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Preferred dividends for EPS calculation.",
            ),
        },
        outputs=[
            HelperOutput(
                name="valuation_ratios",
                type="dict",
                description=(
                    "Dict with market_cap, enterprise_value, eps, book_value_per_share, "
                    "revenue_per_share, pe_ratio, pb_ratio, ps_ratio, ev_to_ebitda, "
                    "ev_to_ebit, ev_to_sales, price_to_cash_flow, price_to_free_cash_flow, "
                    "dividend_yield, peg_ratio."
                ),
            ),
        ],
        produces_artifacts=["ft_valuation_ratios_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
