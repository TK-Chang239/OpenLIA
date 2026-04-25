"""CI gate: every shipped preset must reference only known identifiers."""

from __future__ import annotations

import pytest
from openlia.formula import parse_formula
from openlia.panic_thermometer.panels import PANELS
from openlia.panic_thermometer.presets import PT_PRESETS


def _iter_pt_preset_formulas():
    for panel_id, presets in PT_PRESETS.items():
        panel = PANELS[panel_id]
        known = panel.known_identifiers()
        for preset_name, ruleset in presets.items():
            # Allow params declared in the preset (params override defaults).
            preset_known = set(known) | set((ruleset.get("params") or {}).keys())
            for idx, rule in enumerate(ruleset.get("rules", [])):
                yield (
                    f"{panel_id}.{preset_name}.rule{idx}",
                    rule.get("formula") or "true",
                    preset_known,
                )
            streak = ruleset.get("streak_condition")
            if streak:
                yield (
                    f"{panel_id}.{preset_name}.streak_condition",
                    streak,
                    preset_known,
                )


_PT_CASES = list(_iter_pt_preset_formulas())


@pytest.mark.parametrize("case_id,formula,known", _PT_CASES, ids=[c[0] for c in _PT_CASES])
def test_pt_preset_uses_only_known_identifiers(case_id: str, formula: str, known: set[str]) -> None:
    parsed = parse_formula(formula, known_names=known)
    assert parsed.unknown_identifiers == [], (
        f"{case_id}: formula {formula!r} references unknown identifiers "
        f"{parsed.unknown_identifiers}"
    )
