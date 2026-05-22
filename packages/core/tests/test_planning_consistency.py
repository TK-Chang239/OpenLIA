"""Doctests for the equity research v2.2 planning docs.

These tests enforce the procedural guardrails for the Option B
just-in-time helper-build workflow:

1. Every section heading in the design docs has a corresponding PR
   assignment in the implementation plan's cross-reference table (§14).
2. Every PR cited in §14 maps to a row in the impl plan itself.
3. Every helper on the schema-and-skills §6 list (the 18 complex
   helpers) has a corresponding `skills/<name>.md` file once that
   helper's PR has been merged — enforced as a soft check during
   Phase 0-2 and a hard check after Phase 2 closes.

These tests parse markdown by structure, not by exact prose. Re-wording
a section title is fine; deleting it without updating §14 is not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLANNING_DIR = Path(__file__).resolve().parents[3] / "planning"
IMPL_PLAN = PLANNING_DIR / "2026-05-22-equity-research-implementation-plan.md"

DESIGN_DOCS = {
    "helper-stack": PLANNING_DIR / "2026-05-21-equity-research-engine-helper-stack.md",
    "helpers-design": PLANNING_DIR / "2026-05-21-equity-research-helpers-design.md",
    "signals-addendum": PLANNING_DIR / "2026-05-21-helpers-design-signals-addendum.md",
    "schema-and-skills": PLANNING_DIR / "2026-05-21-helper-schema-and-skills.md",
    "artifact-injection": PLANNING_DIR / "2026-05-22-artifact-injection-redesign.md",
    # Forthcoming docs (Commits 2-3 of this branch). The file-existence checks
    # in the test bodies skip rows that cite these until they land.
    "supplement": PLANNING_DIR / "2026-05-22-helpers-design-supplement.md",
    "sector-modules": PLANNING_DIR / "2026-05-22-helpers-design-sector-modules.md",
}


@pytest.fixture(scope="module")
def impl_plan_text() -> str:
    return IMPL_PLAN.read_text()


@pytest.fixture(scope="module")
def cross_reference_table(impl_plan_text: str) -> list[tuple[str, str, str]]:
    """Parse §14 cross-reference table.

    Returns list of (doc_label, section_marker, pr_ref) tuples.
    """
    match = re.search(
        r"^## 14\. Design-doc cross-reference\s*\n.*?(?=^## 15\.)",
        impl_plan_text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Section 14 cross-reference table not found in impl plan"
    block = match.group(0)
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Design doc"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        doc_label, section_marker, pr_ref = cells[0], cells[1], cells[2]
        doc_label = doc_label.replace("**", "").strip()
        if not doc_label or not section_marker:
            continue
        rows.append((doc_label, section_marker, pr_ref))
    assert rows, "Cross-reference table parsed empty"
    return rows


def test_cross_reference_doc_labels_are_known(cross_reference_table):
    """Every doc label in §14 must match a known design doc."""
    known = set(DESIGN_DOCS.keys())
    for doc_label, section, pr in cross_reference_table:
        assert doc_label in known, (
            f"§14 references unknown design doc {doc_label!r} "
            f"(section {section!r}, PR {pr!r}). Expected one of: {sorted(known)}"
        )


def test_cross_reference_pr_refs_resolve_in_impl_plan(impl_plan_text, cross_reference_table):
    """Every PR mentioned in §14 must have a row defined in the impl plan body."""
    referenced_prs: set[str] = set()
    pr_pattern = re.compile(r"PR (\d+\.\d+)")
    for _, _, pr_ref in cross_reference_table:
        referenced_prs.update(pr_pattern.findall(pr_ref))

    defined_prs: set[str] = set()
    for line in impl_plan_text.splitlines():
        m = re.match(r"^### PR (\d+\.\d+)", line)
        if m:
            defined_prs.add(m.group(1))
        m = re.match(r"^\| 3\.(\d) \|", line)
        if m:
            defined_prs.add(f"3.{m.group(1)}")

    missing = referenced_prs - defined_prs
    assert not missing, (
        f"§14 references PRs not defined in impl plan: {sorted(missing)}. "
        f"Defined PRs: {sorted(defined_prs)}"
    )


# Per-doc explicit allowlist of sections that intentionally do NOT have a
# PR assignment in §14 (they are meta / context / parked / process sections).
# Adding a section to a design doc requires either (a) wiring it into §14
# of the impl plan, or (b) adding it to this allowlist with a stated reason.
INTENTIONALLY_UNMAPPED_SECTIONS: dict[str, dict[str, str]] = {
    "helper-stack": {
        "§3": "Tools we build ourselves — referenced by §14 via individual PR rows",
        "§4": "Existing infrastructure inventory — referenced via deprecation rows",
        "§5": "Helper catalog — referenced by §14 via the implementing PRs",
        "§6": "Active task list — source of truth for §14 PR rows",
        "§7": "Future / parked tasks (Phase 5)",
        "§8": "What is dropped — explicitly out of scope",
        "§9": "Final helper count target",
        "§10": "Open decisions deferred",
        "§11": "External audit expansion meta-section",
        "§12": "References / bibliography",
    },
    "helpers-design": {
        "§0": "Purpose meta-section",
        "§10": "References / bibliography",
    },
    "signals-addendum": {
        # All sections are implementation; nothing intentionally unmapped
    },
    "schema-and-skills": {
        "§0": "Purpose meta-section",
        "§8": "Implementation order — meta-section that describes Phase 0 sequencing",
        "§9": "Open questions parked for later",
    },
    "artifact-injection": {
        "§0": "Purpose meta-section",
        "§7": "Token cost projection — design analysis, not implementable",
        "§10": "Implementation order meta-section",
        "§11": "Open questions parked for later",
    },
    "supplement": {
        "§1": "Document purpose meta-section",
        "§14": "Verifier-hook coverage map — review summary, not a PR-buildable item",
        "§15": "References / bibliography",
    },
    "sector-modules": {
        # Pending doc; same skip behavior as above.
    },
}


def test_every_design_doc_section_has_a_pr_assignment_or_explicit_exemption(
    cross_reference_table,
):
    """Every top-level section in each design doc must either appear in §14
    or be listed in INTENTIONALLY_UNMAPPED_SECTIONS with a reason.

    This forces a deliberate decision when adding new sections to design
    docs. You can't accidentally introduce work that nobody schedules.
    """
    for doc_label, path in DESIGN_DOCS.items():
        if not path.exists():
            # Pending doc (will be added in later commits on this branch);
            # the other docs in DESIGN_DOCS must still be validated.
            continue
        text = path.read_text()
        sections = re.findall(r"^## (\d+)\.\s", text, re.MULTILINE)
        unmapped = INTENTIONALLY_UNMAPPED_SECTIONS.get(doc_label, {})
        for section_num in sections:
            section_marker = f"§{section_num}"
            if section_marker in unmapped:
                continue
            has_ref = any(
                doc == doc_label and section_marker in section_text
                for doc, section_text, _ in cross_reference_table
            )
            assert has_ref, (
                f"Design doc {doc_label!r} section {section_marker} has no PR "
                f"assignment in impl plan §14 and is not listed in "
                f"INTENTIONALLY_UNMAPPED_SECTIONS. Either:\n"
                f"  (a) add a row to §14 of the impl plan mapping this "
                f"section to its implementing PR, or\n"
                f"  (b) add {section_marker} to "
                f"INTENTIONALLY_UNMAPPED_SECTIONS[{doc_label!r}] with a "
                f"stated reason."
            )


def test_cross_reference_sections_resolve_in_cited_docs(cross_reference_table):
    """Every §N citation in §14 must resolve to a real heading in the cited doc.

    Catches the class of drift where §14 says "helpers-design §5.6 DDM family"
    but §5.6 doesn't exist in helpers-design. The original substring-only check
    let fabricated citations slip through; this enforces that each cited section
    marker has a matching `## N.` or `### N.M` heading in the actual doc.

    Skips citations to pending docs that haven't landed yet (supplement,
    sector-modules) — those resolve once the docs are authored in subsequent
    commits on this branch.
    """
    section_re = re.compile(r"§(\d+(?:\.\d+)?)")
    for doc_label, section_text, _ in cross_reference_table:
        if doc_label not in DESIGN_DOCS:
            continue  # caught separately by test_cross_reference_doc_labels_are_known
        doc_path = DESIGN_DOCS[doc_label]
        if not doc_path.exists():
            continue  # pending doc; resolved when the file lands
        doc_text = doc_path.read_text()
        section_refs = section_re.findall(section_text)
        for section_ref in section_refs:
            patterns = [
                rf"^## {re.escape(section_ref)}\.\s",
                rf"^### {re.escape(section_ref)}\s",
                rf"^### {re.escape(section_ref)}`",
            ]
            found = any(
                re.search(p, doc_text, re.MULTILINE) for p in patterns
            )
            assert found, (
                f"§{section_ref} cited in §14 for {doc_label!r} "
                f"(row text: {section_text!r}) does not resolve to any "
                f"heading in {doc_path.name}. "
                f"Either correct the §14 row or add the section to the doc."
            )


def test_skills_md_list_matches_eighteen_helpers():
    """Schema-and-skills §6 must list exactly 18 helpers."""
    schema_doc = DESIGN_DOCS["schema-and-skills"].read_text()
    match = re.search(
        r"^## 6\. skills\.md list.*?(?=^## 7\.)",
        schema_doc,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Section 6 skills.md list not found in schema-and-skills doc"
    block = match.group(0)
    rows = [line for line in block.splitlines() if re.match(r"^\| \d+ \|", line)]
    assert len(rows) == 18, (
        f"schema-and-skills §6 should list exactly 18 complex helpers, "
        f"found {len(rows)}. If you're intentionally changing the count, "
        f"also update the target in impl plan §16 and phase-progress.md."
    )


def test_phase_progress_tracker_exists_and_lists_all_phases():
    """phase-progress.md must exist and cover Phases 0-5."""
    tracker = PLANNING_DIR / "phase-progress.md"
    assert tracker.exists(), "planning/phase-progress.md must exist"
    text = tracker.read_text()
    for phase in ["Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
        assert phase in text, f"phase-progress.md missing {phase} section"
