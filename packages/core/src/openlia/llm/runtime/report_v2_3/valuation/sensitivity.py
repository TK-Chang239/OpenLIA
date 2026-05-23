"""Sensitivity grid — runs the DCF over a 2-D grid of driver values.

Each cell is a fair-value-per-share computed by overriding the base
DCFInputs with one row-driver value and one col-driver value, then
running the standard DCF math.

Locked design: ONE structured fact (SensitivityResult) holding the grid,
not N facts. That keeps it a single citeable unit and lets a writer
reference the whole table with one {{CITE:sensitivity_grid}}.
"""

from __future__ import annotations

from ..schemas import (
    BundleFact,
    ComputedSource,
    DCFInputs,
    ResearchBundle,
    SensitivityInputs,
    SensitivityResult,
)
from .dcf import dcf


def sensitivity(
    inputs: SensitivityInputs, bundle: ResearchBundle
) -> SensitivityResult:
    grid: list[list[float]] = []
    for row_value in inputs.row_values:
        row: list[float] = []
        for col_value in inputs.col_values:
            tweaked = _override_drivers(inputs.base, inputs.row_driver, row_value)
            tweaked = _override_drivers(tweaked, inputs.col_driver, col_value)
            row.append(dcf(tweaked, bundle).fair_value_per_share)
        grid.append(row)

    return SensitivityResult(
        row_driver=inputs.row_driver,
        col_driver=inputs.col_driver,
        row_values=list(inputs.row_values),
        col_values=list(inputs.col_values),
        grid=grid,
    )


def _override_drivers(base: DCFInputs, driver: str, value: float) -> DCFInputs:
    # DCFInputs is a Pydantic BaseModel; model_copy lets us override one field.
    return base.model_copy(update={driver: value})


def sensitivity_result_to_fact(
    result: SensitivityResult, inputs: SensitivityInputs
) -> BundleFact:
    """One BundleFact for the whole grid (locked design from spec §4.2b)."""
    derived = [inputs.base.revenue_base_fact_id, *inputs.base.grounding_fact_ids]
    return BundleFact(
        id="sensitivity_grid",
        label=f"Sensitivity ({result.row_driver} x {result.col_driver})",
        value=f"{len(result.row_values)}x{len(result.col_values)} grid",
        unit=None,
        source=ComputedSource(
            method=f"DCF sensitivity ({result.row_driver} x {result.col_driver})",
            derived_from=derived,
        ),
    )
