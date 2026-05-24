"""VISUALIZE stage — deterministic chart-renderability check.

Per spec §4.5: "Charts are planned at synthesis (the ChartSpec`s already
exist). This stage validates/finalizes specs; it does no new research."
SynthesizeStage already validates that chart fact_ids resolve to the
bundle; this stage adds the *renderability* check that the docx
renderer needs:

  - Every referenced fact exists in the post-COMPUTE bundle (defense in
    depth — SYNTHESIZE checked the pre-COMPUTE bundle).
  - For a series whose single fact is a `BundleSeries`, the series must
    have at least as many points as the chart's category_labels — the
    docx renderer pulls values index-by-index and silently dropping
    cells would be worse than failing here.
  - For a multi-fact-id series, the fact list must be at least as long
    as the category_labels.

Coercion behaviour: instead of raising on a misshapen chart (which would
nuke the entire report), this stage TRUNCATES category_labels / fact-id
lists down to the longest renderable subset, dropping the whole chart
only when nothing usable remains. The LLM routinely emits charts where
``len(category_labels) != len(series.value_fact_ids)``; failing the run
for a one-cell mismatch is a bad cost/benefit. Each truncation/drop is
logged so the divergence stays visible.

No LLM client — VISUALIZE is pure validation. Graceful no-op when
thesis or bundle is absent (incomplete pipeline still in roll-out).
"""

from __future__ import annotations

import logging

from ..schemas import (
    BundleSeries,
    ChartSpec,
    ResearchBundle,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext

log = logging.getLogger(__name__)


class VisualizeStage(Stage):
    slot = V23Slot.VISUALIZE

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        if state.thesis is None or state.bundle is None:
            return state
        kept: list[ChartSpec] = []
        for chart in state.thesis.charts:
            if _coerce_chart_renderability(chart, state.bundle):
                kept.append(chart)
        state.thesis.charts = kept
        return state


def _coerce_chart_renderability(chart: ChartSpec, bundle: ResearchBundle) -> bool:
    """Mutate ``chart`` to a renderable shape; return False to drop it.

    Two classes of fix:
    - Strip ``series.value_fact_ids`` referencing facts the bundle
      doesn't carry (defense in depth — SYNTHESIZE already filters most
      of these).
    - Reconcile any mismatch between ``len(category_labels)`` and
      ``len(series.value_fact_ids)`` / ``BundleSeries.points`` by
      truncating to the common minimum. A chart with one fewer column
      is far better than a failed run.
    """
    bundle_fact_ids = set(bundle.facts.keys())

    # 1) Drop fact_ids that don't resolve. Empty out series accordingly.
    for series in chart.series:
        cleaned = [fid for fid in series.value_fact_ids if fid in bundle_fact_ids]
        if cleaned != series.value_fact_ids:
            dropped = [fid for fid in series.value_fact_ids if fid not in bundle_fact_ids]
            log.warning(
                "VISUALIZE: chart %r series %r stripping unknown fact_ids %s.",
                chart.id,
                series.name,
                sorted(dropped),
            )
            series.value_fact_ids = cleaned

    # Any series with no fact_ids left? Chart is unrenderable — drop it.
    if any(len(s.value_fact_ids) == 0 for s in chart.series):
        log.warning(
            "VISUALIZE: dropping chart %r — at least one series has no resolvable facts.",
            chart.id,
        )
        return False

    # 2) Reconcile the category-count contract per series.
    n_categories = len(chart.category_labels)
    max_renderable = n_categories
    for series in chart.series:
        if len(series.value_fact_ids) == 1:
            fact = bundle.facts[series.value_fact_ids[0]]
            if isinstance(fact.value, BundleSeries):
                max_renderable = min(max_renderable, len(fact.value.points))
            # Scalar fact across multiple categories: renderer handles it
            # (broadcasts the scalar). No constraint.
        else:
            max_renderable = min(max_renderable, len(series.value_fact_ids))

    if max_renderable < n_categories:
        log.warning(
            "VISUALIZE: chart %r truncating from %d to %d categories (LLM under-supplied facts).",
            chart.id,
            n_categories,
            max_renderable,
        )
        chart.category_labels = chart.category_labels[:max_renderable]
        for series in chart.series:
            if len(series.value_fact_ids) > max_renderable:
                series.value_fact_ids = series.value_fact_ids[:max_renderable]

    if not chart.category_labels:
        log.warning("VISUALIZE: dropping chart %r — no renderable categories remain.", chart.id)
        return False

    return True
