"""Dashboard Protocol — every MR dashboard implements this surface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Dashboard(Protocol):
    """Unified interface across T1/T2/T3/T4/T5 dashboards."""

    slug: str
    display_name: str

    # T1 — list of requirement names fetched by the data-provider system.
    T1_REQUIREMENTS: tuple[str, ...]

    # T2 — mapping {indicator_name: formula_string}. Formulas evaluated by
    # FormulaEngine against the fetched data context.
    T2_FORMULAS: dict[str, str]

    # T4 — prompt key used by the LLM runner. None for purely formula-driven
    # dashboards.
    T4_PROMPT_KEY: str | None

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        """Closed-form numpy-based math. May be a no-op for LLM-only dashboards."""
        ...

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        """Return adjusted thresholds when Smart Mode is on. Returns base unchanged if off."""
        ...
