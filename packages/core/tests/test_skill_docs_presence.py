"""Skill doc presence check for the 18 complex helpers — v2.2 engine.

Per the equity research v2.2 plan (schema-and-skills §6 / impl plan §16),
18 helpers MUST have a corresponding `skills/<name>.md` file AND have their
`skill_doc` field wired in the HelperSchema before GA cut.

Strictness policy (per execution-strategy locked decision #4):
- Phase 0-2: warn / skip when complex helpers are not yet registered.
- Phase 2 exit gate onward (v2.2 registry): FAIL for any registered complex
  helper that is missing its skill doc file or has skill_doc=None.

This file contains two test suites:
  1. Legacy `report_v2` path (v2 engine) — skip-based, kept for reference.
  2. `report_v2_2` path (v2.2 engine) — strict FAIL; this is the active gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# v2 engine (legacy — skip-based, no v2 skills dir exists)
_V2_HELPERS = "packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers"
_V2_SKILLS_DIR = REPO_ROOT / _V2_HELPERS / "skills"

# v2.2 engine (active — strict FAIL)
_V2_2_HELPERS = "packages/core/src/openlia/llm/runtime/report_v2_2/tools/library_helpers"
V2_2_SKILLS_DIR = REPO_ROOT / _V2_2_HELPERS / "skills"


# The closed list of 18 complex helpers from schema-and-skills §6.
# Updating this list requires also updating §6 and impl plan §16.
COMPLEX_HELPERS_REQUIRING_SKILL_DOCS: list[str] = [
    "dcf_engine",
    "cost_of_capital_builder",
    "comparables_run",
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


def test_complex_helper_count_is_eighteen() -> None:
    """Sanity: the closed list must be exactly 18 entries."""
    assert len(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS) == 18, (
        f"Expected exactly 18 complex helpers per schema-and-skills §6, "
        f"got {len(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)}. If you're "
        f"intentionally changing the count, update schema-and-skills §6, "
        f"impl plan §16, and phase-progress.md too."
    )


# ---------------------------------------------------------------------------
# Legacy v2 engine — skip-based (no v2 skills dir; kept for reference only)
# ---------------------------------------------------------------------------


def _registered_v2_complex_helpers() -> set[str]:
    """Return complex helpers currently registered in the v2 runtime.

    Returns empty set if the v2 registry isn't importable, making this a no-op.
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
def test_skill_doc_exists_for_registered_complex_helper(helper_name: str) -> None:
    """Legacy v2 engine: skip when not yet registered (Phase 0-2 behaviour).

    This test retains the original warn/skip policy for the v2 engine path.
    The strict FAIL gate lives in the v2.2 suite below.
    """
    registered = _registered_v2_complex_helpers()
    if helper_name not in registered:
        pytest.skip(f"{helper_name} not yet registered in v2 (expected during Phase 0-2)")
    expected_path = _V2_SKILLS_DIR / f"{helper_name}.md"
    assert expected_path.exists(), (
        f"Complex helper {helper_name!r} is registered in the v2 runtime but "
        f"its skill doc is missing at {expected_path}. "
        f"Per impl plan §8 cross-cutting requirement 5, every helper on "
        f"schema-and-skills §6 list must ship its skill doc in the same PR."
    )


# ---------------------------------------------------------------------------
# v2.2 engine — STRICT FAIL (Phase 2 exit gate onward)
#
# Per execution-strategy locked decision #4: once Phase 2 closes, any
# registered complex helper without its skill doc is a hard CI failure.
# There is NO skip path for the v2.2 registry.
# ---------------------------------------------------------------------------


def _get_v2_2_registry() -> dict[str, object]:
    """Return {name: RegisteredHelper} for the v2.2 runtime.

    Raises ImportError propagation if the package isn't installed.
    """
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
        get_helper,
        list_helpers,
    )

    return {h.schema.directory.name: get_helper(h.schema.directory.name) for h in list_helpers()}


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_v2_2_complex_helper_is_registered(helper_name: str) -> None:
    """v2.2: each complex helper from §6 MUST be registered. No skip.

    Per execution-strategy locked decision #4: this becomes a hard FAIL at
    Phase 2 exit gate. If a helper hasn't been built yet, this test tells you.
    """
    registry = _get_v2_2_registry()
    assert helper_name in registry, (
        f"Complex helper {helper_name!r} is NOT registered in the v2.2 "
        f"library_helpers registry. "
        f"Per schema-and-skills §6, all 18 complex helpers must be registered "
        f"at Phase 2 exit gate. Build and register the helper, or remove it "
        f"from COMPLEX_HELPERS_REQUIRING_SKILL_DOCS if the design changed."
    )


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_v2_2_skill_doc_wired_in_schema(helper_name: str) -> None:
    """v2.2: each registered complex helper MUST have skill_doc set (not None). No skip.

    Per execution-strategy locked decision #4: FAIL (not warn) when a complex
    helper registered in v2.2 has skill_doc=None or an empty path.
    """
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    registered = get_helper(helper_name)
    assert registered is not None, (
        f"{helper_name!r} not registered — run test_v2_2_complex_helper_is_registered first."
    )
    skill_doc = registered.schema.skill_doc
    assert skill_doc is not None, (
        f"Complex helper {helper_name!r} has skill_doc=None in its HelperSchema. "
        f"Per execution-strategy locked decision #4 and impl plan §8 requirement 5, "
        f"every §6 complex helper must wire its skill doc via "
        f"SkillDocRef(path='skills/{helper_name}.md', estimated_tokens=...). "
        f"Set skill_doc= in the helper's _SCHEMA definition."
    )
    assert skill_doc.path, (
        f"Complex helper {helper_name!r} has skill_doc with an empty path. "
        f"Set path='skills/{helper_name}.md' (or the filename-safe equivalent)."
    )


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_v2_2_skill_doc_file_exists_on_disk(helper_name: str) -> None:
    """v2.2: the skill doc file declared in schema must exist on disk. No skip.

    Per execution-strategy locked decision #4: FAIL when the referenced
    skills/<name>.md file is absent or empty.
    """
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    registered = get_helper(helper_name)
    if registered is None or not registered.schema.skill_doc:
        pytest.fail(
            f"{helper_name!r}: skill_doc not set — fix test_v2_2_skill_doc_wired_in_schema first."
        )

    skill_doc = registered.schema.skill_doc
    assert skill_doc is not None  # narrowing for mypy
    # skill_doc.path is relative to library_helpers/ (e.g. "skills/dcf_engine.md").
    # Strip leading "skills/" prefix so we can join against V2_2_SKILLS_DIR.
    filename = Path(skill_doc.path).name
    expected_path = V2_2_SKILLS_DIR / filename
    assert expected_path.exists(), (
        f"Complex helper {helper_name!r} declares skill_doc.path={skill_doc.path!r} "
        f"but the file is not found at {expected_path}. "
        f"Create the skill doc or fix the path in SkillDocRef."
    )
    assert expected_path.stat().st_size > 100, (
        f"Skill doc for {helper_name!r} at {expected_path} appears empty (< 100 bytes). "
        f"Add the required sections: Purpose, When to use, When NOT to use, Methodology, "
        f"Common pitfalls, Related helpers."
    )
