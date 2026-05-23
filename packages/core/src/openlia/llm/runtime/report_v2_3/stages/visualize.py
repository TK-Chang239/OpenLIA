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

No LLM client — VISUALIZE is pure validation. Graceful no-op when
thesis or bundle is absent (incomplete pipeline still in roll-out).
"""

from __future__ import annotations

from ..schemas import (
    BundleSeries,
    ChartSpec,
    ResearchBundle,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class VisualizeStage(Stage):
    slot = V23Slot.VISUALIZE

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        if state.thesis is None or state.bundle is None:
            return state
        for chart in state.thesis.charts:
            _validate_chart_renderability(chart, state.bundle)
        return state


def _validate_chart_renderability(
    chart: ChartSpec, bundle: ResearchBundle
) -> None:
    bundle_fact_ids = set(bundle.facts.keys())
    n_categories = len(chart.category_labels)

    for series in chart.series:
        missing = [fid for fid in series.value_fact_ids if fid not in bundle_fact_ids]
        if missing:
            raise RuntimeError(
                f"Chart '{chart.id}' series '{series.name}' references unknown "
                f"facts: {sorted(missing)}"
            )

        if len(series.value_fact_ids) == 1:
            fact = bundle.facts[series.value_fact_ids[0]]
            if isinstance(fact.value, BundleSeries):
                n_points = len(fact.value.points)
                if n_points < n_categories:
                    raise RuntimeError(
                        f"Chart '{chart.id}' series '{series.name}': "
                        f"BundleSeries '{fact.id}' has {n_points} points but "
                        f"the chart needs {n_categories} categories."
                    )
                continue
            # Scalar fact paired with multiple categories is allowed (the
            # docx renderer falls through to scalar mode), but a chart with
            # 0 categories was already prevented by the schema validator.
            continue

        # Multi-fact-id series: one fact per category.
        if len(series.value_fact_ids) < n_categories:
            raise RuntimeError(
                f"Chart '{chart.id}' series '{series.name}': "
                f"{len(series.value_fact_ids)} fact ids supplied but "
                f"{n_categories} categories expected."
            )
