"""analyst_revision_momentum — Upward vs downward estimate revisions, net direction, velocity.

Registered name: "analyst_revision_momentum"
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


def execute(
    revisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute analyst revision momentum.

    Each revision dict: {"period": str, "direction": "up"|"down", "magnitude": float}.
    magnitude is optional (0.0 default) — represents absolute EPS change from revision.

    Args:
        revisions: List of revision records (most recent last or any order).

    Returns:
        Dict with up/down counts, net direction, net score, velocity score.
    """
    if not revisions:
        raise ValueError("revisions must not be empty")

    up_count = 0
    down_count = 0
    total_magnitude = 0.0

    for rev in revisions:
        direction = rev.get("direction", "")
        if direction not in ("up", "down"):
            raise ValueError(f"revision direction must be 'up' or 'down', got {direction!r}")
        magnitude = float(rev.get("magnitude", 0.0))
        if direction == "up":
            up_count += 1
            total_magnitude += magnitude
        else:
            down_count += 1
            total_magnitude -= magnitude

    n = len(revisions)
    net_score = up_count - down_count
    net_direction = "positive" if net_score > 0 else ("negative" if net_score < 0 else "neutral")

    # Velocity: net_score / total revisions (ranges -1 to +1)
    velocity = net_score / n if n > 0 else 0.0

    return {
        "total_revisions": n,
        "up_count": up_count,
        "down_count": down_count,
        "net_score": net_score,
        "net_direction": net_direction,
        "velocity": round(velocity, 3),
        "avg_magnitude": round(total_magnitude / n, 4) if n > 0 else None,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="analyst_revision_momentum",
        category=Category.BUSINESS_QUALITY,
        one_liner="Upward vs downward analyst estimate revisions, net direction, velocity.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Measure analyst sentiment momentum via count of upward vs downward estimate "
            "revisions, net score, and velocity of the revision trend."
        ),
        when_to_use=[
            "Assessing whether analyst consensus is moving toward or away from a stock.",
            "Combining with earnings_surprise_tracker for full estimate momentum picture.",
        ],
        when_not_to_use=[
            "Actual EPS beat/miss tracking — use earnings_surprise_tracker.",
            "Price target changes — not covered by this helper.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revisions": HelperParam(
                type="list[dict]",
                required=True,
                description=(
                    'List of revision records: [{"period": str, "direction": "up"|"down", '
                    '"magnitude": float (optional)}].'
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="analyst_revision_momentum",
                type="dict",
                description=(
                    "total_revisions, up_count, down_count, net_score, "
                    "net_direction, velocity, avg_magnitude."
                ),
            ),
        ],
        produces_artifacts=["analyst_revision_momentum_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
