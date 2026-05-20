"""Forecast and consensus helpers (WS7)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openlia.llm.runtime.report_v2.facts.extractors.compute import union_source_ids
from openlia.llm.runtime.report_v2.facts.helpers._util import oldest_data_as_of_of_deps
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact


def forecast_table(
    history: list[dict],
    consensus: dict,
    growth_assumptions: dict | None = None,
) -> dict:
    """3-year forward table. If consensus is empty, returns empty rows.

    `consensus` keys: revenue_fy1, revenue_fy2, revenue_fy3, eps_fy1, eps_fy2, eps_fy3.
    `growth_assumptions` keys (optional, all per-year overrides): op_margin_pct."""
    growth_assumptions = growth_assumptions or {}
    rev_keys = ["revenue_fy1", "revenue_fy2", "revenue_fy3"]
    eps_keys = ["eps_fy1", "eps_fy2", "eps_fy3"]
    forward_revenue: list[float | None] = [consensus.get(k) for k in rev_keys]
    forward_eps: list[float | None] = [consensus.get(k) for k in eps_keys]
    if all(v is None for v in forward_revenue) and all(v is None for v in forward_eps):
        return {"rows": [], "fabricated": False}
    last_hist_rev = history[-1].get("revenue") if history else None
    rows: list[dict] = []
    prev_rev = last_hist_rev
    for i in range(3):
        rev = forward_revenue[i]
        eps = forward_eps[i]
        growth = None
        if rev is not None and prev_rev is not None and prev_rev != 0:
            growth = (rev / prev_rev) - 1.0
        op_margin = growth_assumptions.get(f"op_margin_fy{i + 1}")
        op_income = rev * op_margin if (rev is not None and op_margin is not None) else None
        net_income = None  # do not fabricate; LLM-supplied if needed
        rows.append(
            {
                "fy_offset": i + 1,
                "revenue": rev,
                "revenue_growth": growth,
                "operating_margin": op_margin,
                "operating_income": op_income,
                "net_income": net_income,
                "eps": eps,
            }
        )
        if rev is not None:
            prev_rev = rev
    return {"rows": rows, "fabricated": False}


def sensitivity_grid(
    base_inputs: dict,
    sweep_dim_a: tuple[str, list[float]],
    sweep_dim_b: tuple[str, list[float]],
    output_fn: Callable[[dict], Any],
) -> dict:
    """Generic 2D sweep across two named input dimensions."""
    a_name, a_vals = sweep_dim_a
    b_name, b_vals = sweep_dim_b
    rows: list[dict] = []
    for a in a_vals:
        for b in b_vals:
            inputs = dict(base_inputs)
            inputs[a_name] = a
            inputs[b_name] = b
            rows.append({a_name: a, b_name: b, "output": output_fn(inputs)})
    return {"rows": rows, "a_name": a_name, "b_name": b_name}


def actual_vs_consensus(
    consensus_eps_fy_next: float | None, our_eps_assumption: float | None
) -> dict:
    if consensus_eps_fy_next is None or our_eps_assumption is None:
        return {
            "consensus": consensus_eps_fy_next,
            "our_estimate": our_eps_assumption,
            "diff_pct": None,
        }
    if consensus_eps_fy_next == 0:
        return {
            "consensus": consensus_eps_fy_next,
            "our_estimate": our_eps_assumption,
            "diff_pct": None,
        }
    diff = (our_eps_assumption - consensus_eps_fy_next) / consensus_eps_fy_next
    return {
        "consensus": consensus_eps_fy_next,
        "our_estimate": our_eps_assumption,
        "diff_pct": diff,
    }


def consensus_vs_assumptions_table(consensus_facts: dict, named_assumptions: list[dict]) -> dict:
    """`named_assumptions`: each {name, our_value, divergence_threshold_pct?}."""
    rows: list[dict] = []
    for a in named_assumptions:
        name = a["name"]
        ours = a.get("our_value")
        cons = consensus_facts.get(name)
        threshold = a.get("divergence_threshold_pct", 0.05)
        diff_pct = None
        diverges = False
        if isinstance(ours, (int, float)) and isinstance(cons, (int, float)) and cons != 0:
            diff_pct = (ours - cons) / cons
            diverges = abs(diff_pct) > threshold
        rows.append(
            {
                "name": name,
                "consensus": cons,
                "our_value": ours,
                "diff_pct": diff_pct,
                "diverges": diverges,
                "source_citation": a.get("source_citation"),
            }
        )
    return {"rows": rows}


# -- Registered Facts -------------------------------------------------------


_FORECAST_DEPS = [
    "revenue_annual",
    "eps_annual",
    "operating_margin_annual",
    "consensus_revenue_fy_next",
    "consensus_revenue_fy_next_plus_one",
    "consensus_revenue_fy_next_plus_two",
    "consensus_eps_fy_next",
    "consensus_eps_fy_next_plus_one",
    "consensus_eps_fy_next_plus_two",
]


@register_fact("forecast_table", tier="compute", depends_on=_FORECAST_DEPS)
def forecast_table_fact(payloads, facts) -> Fact:
    rev_val = facts["revenue_annual"].value
    rev_hist = rev_val if isinstance(rev_val, list) else []
    eps_val = facts["eps_annual"].value
    eps_hist = eps_val if isinstance(eps_val, list) else []
    om_val = facts["operating_margin_annual"].value
    om_hist = om_val if isinstance(om_val, list) else []
    history: list[dict] = []
    n = min(len(rev_hist), len(eps_hist) if eps_hist else len(rev_hist))
    for i in range(n):
        history.append(
            {
                "revenue": rev_hist[i] if i < len(rev_hist) else None,
                "eps": eps_hist[i] if i < len(eps_hist) else None,
                "operating_margin": om_hist[i] if i < len(om_hist) else None,
            }
        )

    def _val(name: str) -> float | None:
        v = facts[name].value
        return v if isinstance(v, (int, float)) else None

    consensus = {
        "revenue_fy1": _val("consensus_revenue_fy_next"),
        "revenue_fy2": _val("consensus_revenue_fy_next_plus_one"),
        "revenue_fy3": _val("consensus_revenue_fy_next_plus_two"),
        "eps_fy1": _val("consensus_eps_fy_next"),
        "eps_fy2": _val("consensus_eps_fy_next_plus_one"),
        "eps_fy3": _val("consensus_eps_fy_next_plus_two"),
    }
    try:
        value = forecast_table(history=history, consensus=consensus)
    except ValueError:
        value = None
    dep_facts = [facts[n] for n in _FORECAST_DEPS]
    return Fact(
        name="forecast_table",
        value=value,
        source_ids=union_source_ids(*dep_facts),
        extractor="compute",
        depends_on=_FORECAST_DEPS,
        data_as_of=oldest_data_as_of_of_deps(dep_facts),
        source_tier="derived",
    )


_AVC_DEPS = ["consensus_eps_fy_next"]


@register_fact("actual_vs_consensus", tier="compute", depends_on=_AVC_DEPS)
def actual_vs_consensus_fact(payloads, facts) -> Fact:
    """The 'our_eps_assumption' input is None at fact-compile time; the
    section dispatcher fills it in. This Fact pre-records the consensus side
    so prose can cite it; the divergence is computed in the section step."""
    cons_f = facts["consensus_eps_fy_next"]
    cons = cons_f.value if isinstance(cons_f.value, (int, float)) else None
    value = actual_vs_consensus(consensus_eps_fy_next=cons, our_eps_assumption=None)
    return Fact(
        name="actual_vs_consensus",
        value=value,
        source_ids=union_source_ids(cons_f),
        extractor="compute",
        depends_on=_AVC_DEPS,
        data_as_of=oldest_data_as_of_of_deps([cons_f]),
        source_tier="derived",
    )
