"""Trading comparables — applies median peer multiples to subject metrics.

For each multiple (e.g. ``ev_ebitda``, ``pe``):
  - Pull the peer multiples from the bundle (``peers[i].metric_fact_ids[multiple]``)
  - Take the median (single peer -> that peer's value)
  - Multiply by the subject's matching metric from
    ``subject_metric_fact_ids[multiple]``
  - Result is the implied value for the subject under that multiple

The output also carries a ``peer_table``: one dict per peer with the
peer's multiples filled in. That's the row data a writer/chart can show
without re-querying the bundle.
"""

from __future__ import annotations

import statistics

from ..schemas import (
    BundleFact,
    CompsInputs,
    CompsResult,
    ComputedSource,
    ResearchBundle,
)


def comps(inputs: CompsInputs, bundle: ResearchBundle) -> CompsResult:
    implied: dict[str, float] = {}
    for multiple in inputs.multiples:
        peer_values = _peer_values_for_multiple(inputs, bundle, multiple)
        if not peer_values:
            continue
        median_multiple = statistics.median(peer_values)
        subject_metric_id = inputs.subject_metric_fact_ids.get(multiple)
        if subject_metric_id is None:
            continue
        subject_metric = _resolve_scalar(bundle, subject_metric_id)
        if subject_metric is None:
            continue
        implied[multiple] = median_multiple * subject_metric

    peer_table: list[dict[str, float]] = []
    for peer in inputs.peers:
        row: dict[str, float] = {}
        for multiple in inputs.multiples:
            fact_id = peer.metric_fact_ids.get(multiple)
            if fact_id is None:
                continue
            value = _resolve_scalar(bundle, fact_id)
            if value is not None:
                row[multiple] = value
        peer_table.append(row)

    return CompsResult(
        implied_value_by_multiple=implied,
        peer_table=peer_table,
    )


def _peer_values_for_multiple(
    inputs: CompsInputs, bundle: ResearchBundle, multiple: str
) -> list[float]:
    values: list[float] = []
    for peer in inputs.peers:
        fact_id = peer.metric_fact_ids.get(multiple)
        if fact_id is None:
            continue
        value = _resolve_scalar(bundle, fact_id)
        if value is not None:
            values.append(value)
    return values


def _resolve_scalar(bundle: ResearchBundle, fact_id: str) -> float | None:
    fact = bundle.facts.get(fact_id)
    if fact is None:
        return None
    value = fact.value
    if isinstance(value, (int, float)):
        return float(value)
    return None


def comps_result_to_facts(result: CompsResult, inputs: CompsInputs) -> list[BundleFact]:
    """Decompose a CompsResult into computed BundleFacts.

    One fact per implied-value multiple, plus the full peer table as a
    string-valued fact so writers can cite it as one unit. Each fact
    cites the inputs that grounded it: the subject's metric fact and the
    peer multiple facts that contributed to the median.
    """
    derived_base: list[str] = []
    for metric_id in inputs.subject_metric_fact_ids.values():
        derived_base.append(metric_id)
    for peer in inputs.peers:
        for metric_id in peer.metric_fact_ids.values():
            derived_base.append(metric_id)
    derived = list(dict.fromkeys(derived_base))

    facts: list[BundleFact] = []
    for multiple, value in result.implied_value_by_multiple.items():
        facts.append(
            BundleFact(
                id=f"comps_implied_{multiple}",
                label=f"Comps implied value ({multiple})",
                value=value,
                unit="USD",
                source=ComputedSource(method=f"Comps median ({multiple})", derived_from=derived),
            )
        )
    return facts
