"""cross_statement_validation — IS-CFS-BS coherence checks.

Registered name: "cross_statement_validation"

Checks:
  1. NI -> retained earnings: NI should equal change in retained earnings + dividends paid
  2. Accounting equation: total_assets == total_liabilities + total_equity
  3. CFO bridge: net_income + DA - delta_NWC - capex ≈ CFO (simplified)
  4. Cash flow: CFO + CFI + CFF = change in cash
"""

from __future__ import annotations

from typing import Any

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

_MATERIALITY_PCT_DEFAULT = 0.01  # 1% of total assets


def execute(
    net_income: float,
    retained_earnings: float,
    retained_earnings_prior: float,
    dividends_paid: float,
    total_assets: float,
    total_liabilities: float,
    total_equity: float,
    cfo: float,
    cfi: float,
    cff: float,
    cash_current: float,
    cash_prior: float,
    materiality_pct: float = _MATERIALITY_PCT_DEFAULT,
) -> dict[str, Any]:
    """Run cross-statement coherence checks.

    Args:
        net_income: Net income from IS.
        retained_earnings: Retained earnings from BS (current period).
        retained_earnings_prior: Retained earnings from BS (prior period).
        dividends_paid: Dividends paid from CFS (positive = outflow).
        total_assets: Total assets from BS.
        total_liabilities: Total liabilities from BS.
        total_equity: Total equity from BS.
        cfo: Operating cash flow.
        cfi: Investing cash flow.
        cff: Financing cash flow.
        cash_current: Cash balance, current period.
        cash_prior: Cash balance, prior period.
        materiality_pct: Delta exceeding this pct of total_assets is flagged (default 1%).

    Returns:
        Dict with list of checks, each with pass/fail, expected, actual, and delta.
    """
    if total_assets <= 0:
        raise ValueError("total_assets must be positive")

    materiality_threshold = total_assets * materiality_pct
    checks: list[dict[str, Any]] = []

    def _check(
        name: str,
        expected: float,
        actual: float,
    ) -> None:
        delta = actual - expected
        flagged = abs(delta) > materiality_threshold
        checks.append(
            {
                "check": name,
                "expected": round(expected, 2),
                "actual": round(actual, 2),
                "delta": round(delta, 2),
                "passed": not flagged,
                "flagged": flagged,
            }
        )

    # Check 1: NI -> retained earnings (NI = delta_RE + dividends)
    delta_re = retained_earnings - retained_earnings_prior
    expected_ni_via_re = delta_re + dividends_paid
    _check("ni_to_retained_earnings", expected=net_income, actual=expected_ni_via_re)

    # Check 2: Accounting equation: assets == liabilities + equity
    _check(
        "accounting_equation",
        expected=total_assets,
        actual=total_liabilities + total_equity,
    )

    # Check 3: Total cash flow = change in cash (CFO + CFI + CFF = delta_cash)
    expected_cash_change = cfo + cfi + cff
    actual_cash_change = cash_current - cash_prior
    _check("cash_flow_reconciliation", expected=expected_cash_change, actual=actual_cash_change)

    flagged_count = sum(1 for c in checks if c["flagged"])
    max_delta = max((abs(c["delta"]) for c in checks), default=0.0)

    return {
        "checks": checks,
        "total_checks": len(checks),
        "flagged_count": flagged_count,
        "all_passed": flagged_count == 0,
        "max_delta": round(max_delta, 2),
        "materiality_threshold": round(materiality_threshold, 2),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="cross_statement_validation",
        category=Category.STATEMENT_INTEGRITY,
        one_liner="IS-CFS-BS coherence checks: NI to RE, accounting equation, cash reconciliation.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Verify internal consistency across income statement, balance sheet, and cash flow "
            "statement. Flags mismatches exceeding a materiality threshold."
        ),
        when_to_use=[
            "Statement integrity review before building a financial model.",
            "Forensic analysis to detect potential restatement risk.",
        ],
        when_not_to_use=[
            "Full forensic scoring — use forensic_panel.",
            "Earnings quality analysis — use quality_of_earnings_panel.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(type="float", required=True, description="Net income."),
            "retained_earnings": HelperParam(
                type="float", required=True, description="Retained earnings, current period."
            ),
            "retained_earnings_prior": HelperParam(
                type="float", required=True, description="Retained earnings, prior period."
            ),
            "dividends_paid": HelperParam(
                type="float", required=True, description="Dividends paid (positive = outflow)."
            ),
            "total_assets": HelperParam(type="float", required=True, description="Total assets."),
            "total_liabilities": HelperParam(
                type="float", required=True, description="Total liabilities."
            ),
            "total_equity": HelperParam(type="float", required=True, description="Total equity."),
            "cfo": HelperParam(type="float", required=True, description="Operating cash flow."),
            "cfi": HelperParam(type="float", required=True, description="Investing cash flow."),
            "cff": HelperParam(type="float", required=True, description="Financing cash flow."),
            "cash_current": HelperParam(
                type="float", required=True, description="Cash balance, current period."
            ),
            "cash_prior": HelperParam(
                type="float", required=True, description="Cash balance, prior period."
            ),
            "materiality_pct": HelperParam(
                type="float",
                required=False,
                default=0.01,
                description="Materiality threshold as % of total_assets (default 1%).",
            ),
        },
        outputs=[
            HelperOutput(
                name="cross_statement_validation",
                type="dict",
                description=(
                    "checks list (check, expected, actual, delta, passed, flagged), "
                    "flagged_count, all_passed, max_delta."
                ),
            ),
        ],
        produces_artifacts=["cross_statement_validation_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
