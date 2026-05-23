"""Discounted cash flow.

Inputs (validated by DCFInputs in schemas):
  - revenue_base: looked up from `bundle.facts[revenue_base_fact_id].value`
  - per-year growth path -> revenue trajectory
  - per-year margin path -> FCF trajectory (after-tax)
  - WACC -> annual discount factor
  - terminal_growth -> Gordon-growth perpetuity at the end of the
    explicit period

Optional grounding facts (looked up by id from ``grounding_fact_ids``
when present in the bundle):
  - ``net_debt`` (USD millions) -> bridges enterprise value to equity
  - ``shares_outstanding`` (count, millions) -> divides equity value
    into a per-share fair value

When either grounding fact is missing the corresponding output stays
loosely defined: equity_value falls back to enterprise_value, and
fair_value_per_share falls back to equity_value. Callers that want a
defensible per-share number must supply those grounding facts.
"""

from __future__ import annotations

from ..schemas import DCFInputs, DCFResult, ResearchBundle

_NET_DEBT_FACT_ID = "net_debt"
_SHARES_FACT_ID = "shares_outstanding"


def dcf(inputs: DCFInputs, bundle: ResearchBundle) -> DCFResult:
    """Run a 2-stage DCF given inputs + the bundle that grounds them.

    Stage 1: project FCF over the explicit horizon (length of growth_path).
    Stage 2: terminal value via Gordon growth at the last FCF.
    """
    base_revenue = _resolve_scalar(bundle, inputs.revenue_base_fact_id)
    if base_revenue is None:
        raise RuntimeError(
            f"DCF revenue base fact '{inputs.revenue_base_fact_id}' missing "
            f"or non-scalar in bundle."
        )

    if inputs.wacc <= inputs.terminal_growth:
        raise RuntimeError(
            f"DCF requires wacc ({inputs.wacc}) > terminal_growth "
            f"({inputs.terminal_growth}) for Gordon-growth terminal value."
        )

    revenues: list[float] = []
    fcfs: list[float] = []
    rev = base_revenue
    for growth, margin in zip(inputs.revenue_growth_path, inputs.margin_path, strict=True):
        rev = rev * (1.0 + growth)
        revenues.append(rev)
        fcfs.append(rev * margin * (1.0 - inputs.tax_rate))

    # Discount explicit-period FCFs to year 0 (mid-year convention skipped
    # for now — that's a refinement that requires a flag we don't model
    # yet; end-of-year is the conventional default).
    discount_factor = 1.0 + inputs.wacc
    pv_explicit = sum(fcf / (discount_factor ** (year + 1)) for year, fcf in enumerate(fcfs))

    horizon = len(fcfs)
    terminal_fcf = fcfs[-1] * (1.0 + inputs.terminal_growth)
    terminal_value = terminal_fcf / (inputs.wacc - inputs.terminal_growth)
    pv_terminal = terminal_value / (discount_factor ** horizon)

    enterprise_value = pv_explicit + pv_terminal

    grounding = set(inputs.grounding_fact_ids)
    net_debt = (
        _resolve_scalar(bundle, _NET_DEBT_FACT_ID)
        if _NET_DEBT_FACT_ID in grounding
        else None
    )
    shares = (
        _resolve_scalar(bundle, _SHARES_FACT_ID)
        if _SHARES_FACT_ID in grounding
        else None
    )

    equity_value = enterprise_value - net_debt if net_debt is not None else enterprise_value
    if shares and shares > 0:
        fair_value_per_share = equity_value / shares
    else:
        fair_value_per_share = equity_value

    return DCFResult(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        fair_value_per_share=fair_value_per_share,
    )


def _resolve_scalar(bundle: ResearchBundle, fact_id: str) -> float | None:
    fact = bundle.facts.get(fact_id)
    if fact is None:
        return None
    value = fact.value
    if isinstance(value, (int, float)):
        return float(value)
    return None
