"""common_size_statements — IS/BS/CFS as % of revenue or total assets.

Registered name: "common_size_statements"
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


def _pct(val: float | None, base: float) -> float | None:
    if val is None or base == 0:
        return None
    return round(val / base * 100.0, 2)


def execute(
    income_statement: dict[str, float],
    balance_sheet: dict[str, float] | None = None,
    cash_flow_statement: dict[str, float] | None = None,
    peer_income_statement: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute common-size financial statements.

    IS items are expressed as % of revenue.
    BS items are expressed as % of total_assets.
    CFS items are expressed as % of revenue.

    Each statement dict should use standard line-item keys.
    Required IS key: "revenue". Required BS key: "total_assets" (if BS provided).

    Args:
        income_statement: Dict of IS line items including "revenue".
        balance_sheet: Optional dict of BS line items including "total_assets".
        cash_flow_statement: Optional dict of CFS line items including "revenue" or
            uses income_statement revenue.
        peer_income_statement: Optional peer IS for comparison (same keys as income_statement).

    Returns:
        Dict with common_size_is, common_size_bs, common_size_cfs, and peer deltas.
    """
    revenue = income_statement.get("revenue")
    if revenue is None:
        raise ValueError("income_statement must include 'revenue'")

    # IS common-size
    common_size_is = {k: _pct(v, revenue) for k, v in income_statement.items()}
    common_size_is["_base"] = "revenue"

    # BS common-size
    common_size_bs: dict[str, Any] | None = None
    if balance_sheet is not None:
        total_assets = balance_sheet.get("total_assets")
        if total_assets is None:
            raise ValueError("balance_sheet must include 'total_assets'")
        common_size_bs = {k: _pct(v, total_assets) for k, v in balance_sheet.items()}
        common_size_bs["_base"] = "total_assets"

    # CFS common-size (use revenue as base)
    common_size_cfs: dict[str, Any] | None = None
    if cash_flow_statement is not None:
        common_size_cfs = {k: _pct(v, revenue) for k, v in cash_flow_statement.items()}
        common_size_cfs["_base"] = "revenue"

    # Peer delta (IS only)
    peer_delta: dict[str, float | None] | None = None
    if peer_income_statement is not None:
        peer_revenue = peer_income_statement.get("revenue")
        if peer_revenue:
            peer_cs = {k: _pct(v, peer_revenue) for k, v in peer_income_statement.items()}
            peer_delta = {}
            for k in common_size_is:
                if k == "_base":
                    continue
                subject_val = common_size_is.get(k)
                peer_val = peer_cs.get(k)
                if subject_val is not None and peer_val is not None:
                    peer_delta[k] = round(subject_val - peer_val, 2)
                else:
                    peer_delta[k] = None

    return {
        "common_size_is": common_size_is,
        "common_size_bs": common_size_bs,
        "common_size_cfs": common_size_cfs,
        "peer_is_delta": peer_delta,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="common_size_statements",
        category=Category.BUSINESS_QUALITY,
        one_liner="IS/BS/CFS as % of revenue or total assets, with optional peer delta.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Express financial statements in common-size form: IS and CFS as % of revenue, "
            "BS as % of total assets. Optional peer comparison deltas."
        ),
        when_to_use=[
            "Comparing cost structure and margins to peers.",
            "Tracking margin composition changes over time.",
        ],
        when_not_to_use=[
            "Growth rate analysis — use ft_growth_metrics.",
            "Ratio analysis — use ft_profitability_ratios or ratio_calculator.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "income_statement": HelperParam(
                type="dict[str, float]",
                required=True,
                description='IS line items including "revenue".',
            ),
            "balance_sheet": HelperParam(
                type="dict[str, float] | None",
                required=False,
                default=None,
                description='Optional BS line items including "total_assets".',
            ),
            "cash_flow_statement": HelperParam(
                type="dict[str, float] | None",
                required=False,
                default=None,
                description="Optional CFS line items (expressed as % of revenue).",
            ),
            "peer_income_statement": HelperParam(
                type="dict[str, float] | None",
                required=False,
                default=None,
                description="Optional peer IS for delta comparison.",
            ),
        },
        outputs=[
            HelperOutput(
                name="common_size_statements",
                type="dict",
                description="common_size_is, common_size_bs, common_size_cfs, peer_is_delta.",
            ),
        ],
        produces_artifacts=["common_size_statements_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
