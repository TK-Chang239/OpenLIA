"""Derive the cross-department MRSnapshot fields from cached dashboard
payloads. Preserves the contract Morning Briefing reads."""

from __future__ import annotations

from openlia.macro_research.payloads import DebtCycleData


def debt_cycle_phase_from_payload(payload: DebtCycleData) -> str:
    return payload.phaseBox.title
