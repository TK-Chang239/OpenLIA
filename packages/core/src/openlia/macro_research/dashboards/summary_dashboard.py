"""Summary — cross-framework synthesis of the five Dalio dashboards.

Unlike T1-T5, Summary is a pure aggregation view: it has no deterministic
classifier and no per-indicator compute. Its inputs are the other five
dashboards' cached payloads, injected by the server, and the LLM synthesizes
one SummaryData payload from them. It therefore implements only the identity
attributes (``slug``/``display_name``) the route layer reads; the compute hooks
on the Dashboard Protocol are no-ops for this view.
"""

from __future__ import annotations

from typing import Any, ClassVar


class SummaryDashboard:
    slug = "summary"
    display_name = "Summary"

    T1_REQUIREMENTS: ClassVar[tuple[str, ...]] = ()

    T2_FORMULAS: ClassVar[dict[str, str]] = {}

    T4_PROMPT_KEY: str | None = "summary"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        return {}

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        return dict(base_thresholds)
