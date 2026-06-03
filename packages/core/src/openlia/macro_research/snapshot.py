"""Derive the cross-department MRSnapshot fields from cached dashboard
payloads. Preserves the contract Morning Briefing reads."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import ValidationError

from openlia.macro_research.payloads import DebtCycleData, FiveForcesData, FourSeasonsData

_log = logging.getLogger(__name__)

_LEADING_INT = re.compile(r"^\s*(\d+)")


def debt_cycle_phase_from_payload(payload: DebtCycleData) -> str:
    return payload.phaseBox.title


def active_force_count_from_payload(payload: FiveForcesData) -> int:
    """Return the active-force count the FiveForcesView renders.

    The view shows ``loops.active.countText`` (e.g. ``"3 / 5"`` or
    ``"3 active"``); the active count is its leading integer. A countText with
    no leading integer is invalid and raises ValueError.
    """
    match = _LEADING_INT.match(payload.loops.active.countText)
    if match is None:
        raise ValueError(
            f"FiveForcesData countText has no leading integer: {payload.loops.active.countText!r}"
        )
    return int(match.group(1))


def economic_season_from_payload(payload: FourSeasonsData) -> str:
    """Return the season name of the quadrant cell the now-marker visually
    occupies, matching exactly what FourSeasonsView renders.

    The view positions each marker with `top: ${yPct}%` and `left: ${xPct}%`,
    so yPct < 50 is the top row and xPct < 50 is the left column. The active
    marker is the one with variant "now"; if none exists, the first marker is
    used. FourSeasonsData with no markers is invalid and raises ValueError.
    """
    markers = payload.quadrant.markers
    if not markers:
        raise ValueError("FourSeasonsData has no quadrant markers")

    marker = next((m for m in markers if m.variant == "now"), markers[0])
    seasons = payload.quadrant.seasons

    top = marker.yPct < 50
    left = marker.xPct < 50
    if top:
        cell = seasons.tl if left else seasons.tr
    else:
        cell = seasons.bl if left else seasons.br
    return cell.name


_DERIVERS = {
    "debt_cycle": (DebtCycleData, debt_cycle_phase_from_payload),
    "four_seasons": (FourSeasonsData, economic_season_from_payload),
    "five_forces": (FiveForcesData, active_force_count_from_payload),
}


def snapshot_value_for(dashboard: str, payload: dict[str, Any]) -> str | int | None:
    """Derive the cross-department snapshot value for one cached dashboard
    payload. Returns None for dashboards that contribute no snapshot field, or
    when a cached payload cannot be validated/derived. The latter is a
    DELIBERATE degrade-not-crash: this feeds a read-only cross-department view,
    and a stale/legacy-schema cached payload must not break the consumer. The
    failure is logged (warning + exc_info) so it is never silent."""
    entry = _DERIVERS.get(dashboard)
    if entry is None:
        return None
    model_cls, helper = entry
    try:
        return helper(model_cls.model_validate(payload))
    except (ValidationError, ValueError, KeyError, TypeError):
        _log.warning("snapshot derivation failed for dashboard %r", dashboard, exc_info=True)
        return None
