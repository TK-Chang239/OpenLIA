"""Derive the cross-department MRSnapshot fields from cached dashboard
payloads. Preserves the contract Morning Briefing reads."""

from __future__ import annotations

from openlia.macro_research.payloads import DebtCycleData, FourSeasonsData


def debt_cycle_phase_from_payload(payload: DebtCycleData) -> str:
    return payload.phaseBox.title


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
