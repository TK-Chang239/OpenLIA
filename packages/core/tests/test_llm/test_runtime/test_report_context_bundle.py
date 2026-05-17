from __future__ import annotations

import random
import string
from pathlib import Path

from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.report_context_bundle import (
    BUNDLE_DEFAULT_MAX_BYTES,
    ReportContextBundle,
    load_bundle,
    persist_bundle,
)
from openlia.llm.runtime.section_draft import SectionDraft


def _plan() -> ReportPlan:
    return ReportPlan.model_validate(
        {
            "company_thesis": "thesis",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                {
                    "section_id": "company_overview",
                    "title": "Overview",
                    "narrative_goal": "goal",
                    "key_questions": ["q1", "q2", "q3"],
                    "target_depth": "standard",
                    "word_budget": 200,
                    "data_paths": [
                        {
                            "tool_name": "eodhd__get_fundamentals_data",
                            "tool_arguments": {"ticker": "MSFT.US"},
                            "path": "General",
                            "purpose": "background",
                        }
                    ],
                    "cross_refs": [],
                }
            ],
        }
    )


def _draft() -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": [{"type": "text", "content": "Body."}],
            "citations_used": ["c1"],
            "word_count": 1,
            "open_questions": [],
        }
    )


def test_bundle_roundtrips_through_persist_and_load(tmp_path: Path) -> None:
    bundle = ReportContextBundle(
        plan=_plan(),
        fetched_data={
            'eodhd__get_fundamentals_data({"ticker":"MSFT.US"}):General': {"hq": "Redmond"}
        },
        section_drafts=[_draft()],
        payload_refs={"r_abc_01": {"any": "payload"}},
        generation_meta={
            "model_id": "fake-1",
            "total_input_tokens": 1,
            "total_output_tokens": 1,
            "web_search_count": 0,
            "schema_version": "1.0",
        },
    )
    path = tmp_path / "bundles" / "r_test.json.gz"
    persist_bundle(bundle, path=path)
    assert path.exists()
    loaded = load_bundle(path)
    assert loaded.plan.company_thesis == "thesis"
    assert loaded.fetched_data == bundle.fetched_data
    assert loaded.payload_refs == bundle.payload_refs
    assert loaded.section_drafts[0].section_id == "company_overview"


def test_persist_truncates_largest_payload_refs_when_over_cap(tmp_path: Path) -> None:
    # Use random (incompressible) data so gzip cannot shrink it below the cap.
    rng = random.Random(42)
    rand_str = "".join(rng.choices(string.ascii_letters + string.digits, k=200_000))
    huge = {"big": rand_str}
    refs = {f"r_{i:03d}": dict(huge) for i in range(60)}  # forces > 5 MiB compressed
    bundle = ReportContextBundle(
        plan=_plan(),
        fetched_data={},
        section_drafts=[_draft()],
        payload_refs=refs,
        generation_meta={
            "model_id": "fake-1",
            "total_input_tokens": 1,
            "total_output_tokens": 1,
            "web_search_count": 0,
            "schema_version": "1.0",
        },
    )
    path = tmp_path / "r_truncate.json.gz"
    truncated_keys = persist_bundle(
        bundle, path=path, max_bytes=1_000_000
    )  # 1 MiB cap forces truncation
    assert path.exists()
    assert truncated_keys, "expected some refs to be dropped under tight cap"
    loaded = load_bundle(path)
    # Plan and section_drafts always kept.
    assert loaded.plan.company_thesis == "thesis"
    assert loaded.section_drafts[0].section_id == "company_overview"
    # Some payload_refs are dropped; bundle_truncated metadata records which.
    assert len(loaded.payload_refs) < len(refs)
    assert "bundle_truncated" in loaded.generation_meta
    assert isinstance(loaded.generation_meta["bundle_truncated"], list)


def test_default_max_bytes_is_five_mebibytes() -> None:
    assert BUNDLE_DEFAULT_MAX_BYTES == 5 * 1024 * 1024
