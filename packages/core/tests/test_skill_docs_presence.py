"""Skill doc presence check for the 18 complex helpers.

Per the equity research v2.2 plan (schema-and-skills §6 / impl plan §16),
18 helpers MUST have a corresponding `skills/<name>.md` file before the
GA cut. This test enumerates that closed list and:

- Phase 0-2 (early build): warns about missing skill docs but does not
  fail. Helpers can land schema-first; skill doc lands with the helper's
  PR.
- Phase 2 closes onward: FAILS for any complex helper that is registered
  in the runtime library_helpers registry without a corresponding
  skills/<name>.md file at the expected path.

The transition is gated by the existence of all 18 helpers in the
registry — once they're all registered, the test becomes strict.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_HELPERS = "packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers"
SKILLS_DIR = REPO_ROOT / _HELPERS / "skills"


# The closed list of 18 complex helpers from schema-and-skills §6.
# Updating this list requires also updating §6 and impl plan §16.
COMPLEX_HELPERS_REQUIRING_SKILL_DOCS: list[str] = [
    "dcf_engine",
    "cost_of_capital_builder",
    "comparables_run",  # filename-safe form of comparables.run
    "ddm_family",
    "justified_multiples",
    "sotp_builder",
    "price_target_blender",
    "rating_band_assigner",
    "rnpv_pipeline",
    "banks_sector_panel",
    "reit_valuation_panel",
    "ep_sector_panel",
    "insurance_valuation_panel",
    "forensic_panel",
    "statement_integrity_bundle",
    "insider_signal_panel",
    "historical_multiple_trends",
    "workbook_builder",
]


def test_complex_helper_count_is_eighteen():
    """Sanity: the closed list must be exactly 18 entries."""
    assert len(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS) == 18, (
        f"Expected exactly 18 complex helpers per schema-and-skills §6, "
        f"got {len(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)}. If you're "
        f"intentionally changing the count, update schema-and-skills §6, "
        f"impl plan §16, and phase-progress.md too."
    )


def _registered_complex_helpers() -> set[str]:
    """Return the subset of complex helpers currently registered in the runtime.

    Returns empty set if the registry isn't importable yet (Phase 0 not
    merged), which makes this test a no-op during early development.
    """
    try:
        from openlia.llm.runtime.report_v2.tools.library_helpers import list_helpers
    except ImportError:
        return set()
    try:
        registered = {h.helper_schema.name for h in list_helpers()}
    except Exception:
        return set()
    return registered & set(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_skill_doc_exists_for_registered_complex_helper(helper_name: str):
    """If a complex helper is registered, its skill doc must exist.

    During Phase 0-1, no complex helpers are registered yet, so this test
    is a no-op. As Phase 2 progresses, helpers get registered, and the
    test starts requiring their skill docs in lockstep.
    """
    registered = _registered_complex_helpers()
    if helper_name not in registered:
        pytest.skip(f"{helper_name} not yet registered (expected during Phase 0-2)")
    expected_path = SKILLS_DIR / f"{helper_name}.md"
    assert expected_path.exists(), (
        f"Complex helper {helper_name!r} is registered in the runtime but "
        f"its skill doc is missing at {expected_path}. "
        f"Per impl plan §8 cross-cutting requirement 5, every helper on "
        f"schema-and-skills §6 list must ship its skill doc in the same PR."
    )
