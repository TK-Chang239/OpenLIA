"""one_time_item_identification — Flags impairments, restructuring, gains/losses on sale.

Registered name: "one_time_item_identification"

One-time item types recognized:
  impairment, restructuring, gain_on_sale, loss_on_sale, ipo_cost, ma_cost,
  litigation, asset_write_down, other_nonrecurring
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

_KNOWN_TYPES = frozenset(
    {
        "impairment",
        "restructuring",
        "gain_on_sale",
        "loss_on_sale",
        "ipo_cost",
        "ma_cost",
        "litigation",
        "asset_write_down",
        "other_nonrecurring",
    }
)


def execute(
    items: list[dict[str, Any]],
    net_income: float | None = None,
) -> dict[str, Any]:
    """Identify and classify one-time items.

    Each item dict: {"name": str, "type": str, "amount": float, "tax_rate": float (optional)}.
    amount: positive = benefit to NI (e.g., gain on sale), negative = charge (e.g., impairment).

    Args:
        items: List of one-time item records.
        net_income: Reported net income. If provided, computes pct of NI impact.

    Returns:
        Dict with classified items, total impact, and % of NI if provided.
    """
    if not items:
        raise ValueError("items must not be empty")

    classified: list[dict[str, Any]] = []
    total_pretax_impact = 0.0

    for item in items:
        name = item.get("name", "")
        item_type = item.get("type", "other_nonrecurring")
        amount = float(item.get("amount", 0.0))
        tax_rate = float(item.get("tax_rate", 0.0))

        if item_type not in _KNOWN_TYPES:
            item_type = "other_nonrecurring"

        after_tax = amount * (1.0 - tax_rate) if tax_rate > 0 else amount
        polarity = "charge" if amount < 0 else "benefit"
        total_pretax_impact += amount

        classified.append(
            {
                "name": name,
                "type": item_type,
                "pretax_amount": round(amount, 2),
                "tax_rate": tax_rate,
                "after_tax_amount": round(after_tax, 2),
                "polarity": polarity,
            }
        )

    total_after_tax = sum(c["after_tax_amount"] for c in classified)
    pct_of_ni: float | None = None
    if net_income is not None and net_income != 0:
        pct_of_ni = round(total_after_tax / abs(net_income) * 100.0, 2)

    # Type summary
    by_type: dict[str, float] = {}
    for c in classified:
        by_type.setdefault(c["type"], 0.0)
        by_type[c["type"]] += c["after_tax_amount"]

    return {
        "items": classified,
        "total_pretax_impact": round(total_pretax_impact, 2),
        "total_after_tax_impact": round(total_after_tax, 2),
        "pct_of_net_income": pct_of_ni,
        "by_type": {k: round(v, 2) for k, v in by_type.items()},
        "item_count": len(classified),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="one_time_item_identification",
        category=Category.FORENSIC,
        one_liner="Classify and quantify one-time items: impairments, restructuring, gains/losses.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Identify, classify, and quantify non-recurring items in the income statement. "
            "Produces after-tax impact and % of reported NI."
        ),
        when_to_use=[
            "Adjusting reported NI to normalized / recurring basis.",
            "Feeding one-time item data into forensic_panel.",
        ],
        when_not_to_use=[
            "Full forensic scoring — use forensic_panel.",
            "Earnings quality with accruals — use quality_of_earnings_panel.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "items": HelperParam(
                type="list[dict]",
                required=True,
                description=(
                    'List: [{"name": str, "type": str, "amount": float, "tax_rate": float}]. '
                    "Types: impairment, restructuring, gain_on_sale, loss_on_sale, "
                    "ipo_cost, ma_cost, litigation, asset_write_down, other_nonrecurring."
                ),
            ),
            "net_income": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Reported net income. If provided, computes % of NI impact.",
            ),
        },
        outputs=[
            HelperOutput(
                name="one_time_items",
                type="dict",
                description=(
                    "items list (classified), total_pretax_impact, total_after_tax_impact, "
                    "pct_of_net_income, by_type summary."
                ),
            ),
        ],
        produces_artifacts=["one_time_item_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
