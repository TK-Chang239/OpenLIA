from __future__ import annotations

from openlia.llm.runtime.report_v2.pipeline.verifier_deterministic import (
    detect_artifact_missing,
    detect_block_shape,
    detect_citation_orphaned,
    detect_citation_unresolved,
    detect_tombstone,
    detect_year_slip,
)


def test_block_shape_flags_empty_prose():
    issues = detect_block_shape("s1", [{"type": "prose", "text": ""}])
    assert any(i.issue_type == "block_shape" for i in issues)
    assert all(i.severity == "blocker" for i in issues)
    assert all(i.detector == "deterministic" for i in issues)


def test_block_shape_flags_table_missing_headers():
    issues = detect_block_shape("s1", [{"type": "table", "rows": [["a", "b"]]}])
    assert any(i.issue_type == "block_shape" for i in issues)


def test_block_shape_clean_prose_and_table():
    issues = detect_block_shape(
        "s1",
        [
            {"type": "prose", "text": "Revenue grew 10%."},
            {"type": "table", "headers": ["Metric", "Value"], "rows": []},
        ],
    )
    assert issues == []


def test_tombstone_flags_placeholder():
    issues = detect_tombstone("s1", [{"type": "prose", "text": "[placeholder] Q3 revenue grew"}])
    assert any(i.issue_type == "tombstone" for i in issues)
    assert all(i.detector == "deterministic" for i in issues)


def test_tombstone_flags_tbd():
    issues = detect_tombstone("s1", [{"type": "prose", "text": "TBD — awaiting data"}])
    assert any(i.issue_type == "tombstone" for i in issues)


def test_tombstone_flags_as_an_ai():
    blocks = [{"type": "prose", "text": "As an AI I cannot verify this claim."}]
    issues = detect_tombstone("s1", blocks)
    assert any(i.issue_type == "tombstone" for i in issues)


def test_tombstone_clean_prose():
    issues = detect_tombstone("s1", [{"type": "prose", "text": "Revenue grew 10% YoY."}])
    assert issues == []


def test_year_slip_flags_mismatched_year():
    issues = detect_year_slip(
        section_id="s1",
        blocks=[{"type": "prose", "text": "FY2024 revenue [c:c1] reached $94B."}],
        citations={"c1": {"retrieved_at": "2026-02-01", "title": "FY2026 filing"}},
    )
    assert any(i.issue_type == "year_slip" for i in issues)
    assert all(i.severity == "blocker" for i in issues)


def test_year_slip_no_slip_within_one_year():
    issues = detect_year_slip(
        section_id="s1",
        blocks=[{"type": "prose", "text": "FY2025 revenue [c:c1] reached $94B."}],
        citations={"c1": {"retrieved_at": "2026-01-15", "title": "FY2025 annual"}},
    )
    assert issues == []


def test_year_slip_missing_citation_tolerated():
    issues = detect_year_slip(
        section_id="s1",
        blocks=[{"type": "prose", "text": "FY2024 revenue [c:missing] grew."}],
        citations={},
    )
    assert issues == []


def test_citation_unresolved_flags_unknown_id():
    issues = detect_citation_unresolved(
        "s1",
        [{"type": "prose", "text": "Revenue [c:ghost] grew."}],
        pool_citation_ids={"real_id"},
    )
    assert any(i.issue_type == "citation_unresolved" for i in issues)
    assert all(i.severity == "blocker" for i in issues)


def test_citation_unresolved_clean():
    issues = detect_citation_unresolved(
        "s1",
        [{"type": "prose", "text": "Revenue [c:real_id] grew."}],
        pool_citation_ids={"real_id"},
    )
    assert issues == []


def test_citation_orphaned_flags_unused_pool_id():
    issues = detect_citation_orphaned(
        used_ids={"c1"},
        pool_citation_ids={"c1", "c2", "c3"},
    )
    assert len(issues) == 2
    assert all(i.issue_type == "citation_orphaned" for i in issues)
    assert all(i.severity == "warning" for i in issues)
    assert all(i.section_id is None for i in issues)


def test_citation_orphaned_all_used():
    issues = detect_citation_orphaned(used_ids={"c1", "c2"}, pool_citation_ids={"c1", "c2"})
    assert issues == []


def test_artifact_missing_flags_unreembedded():
    issues = detect_artifact_missing(
        required_artifact_ids={"art1", "art2"},
        embedded_artifact_ids={"art1"},
    )
    assert len(issues) == 1
    assert issues[0].issue_type == "artifact_missing"
    assert issues[0].severity == "blocker"
    assert issues[0].detector == "deterministic"


def test_artifact_missing_all_embedded():
    issues = detect_artifact_missing(
        required_artifact_ids={"art1"},
        embedded_artifact_ids={"art1"},
    )
    assert issues == []
