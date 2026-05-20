"""Tests for the PR 5 lift: first-person voice check reads SectionSpec.voice.

The previous hardcoded section allowlist (`{"analyst_view","investment_recommendation"}`)
is now a per-section opt-in: when a template's `SectionSpec.voice` is
`"third_person_only"`, the section's prose is gated against first-person
advocacy. Sections with `voice="any"` (the default) skip the check.

When `validate_sections` is called without a `template`, the legacy
hardcoded behavior persists so existing callers continue to work unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.types import Fact
from openlia.llm.runtime.report_v2.validators import validate_sections


def _fact(name: str, value: float) -> Fact:
    return Fact(
        name=name,
        value=value,
        source_ids=[0],
        extractor="deterministic",
        data_as_of=datetime.now(UTC),
    )


_PROSE_WITH_FIRST_PERSON = "Some lead-in. We believe the company will continue to outperform. End."


def test_legacy_behavior_persists_when_no_template_provided() -> None:
    # Backward compat: no template means the hardcoded allowlist
    # ({"analyst_view","investment_recommendation"}) still fires.
    report = validate_sections(
        section_files={"investment_recommendation": _PROSE_WITH_FIRST_PERSON},
        facts={},
    )

    first_person = [f for f in report.failures if f.failure_type == "first_person_voice"]
    assert len(first_person) == 1


def test_template_section_with_voice_any_is_not_gated() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    template = TemplateSpec(
        name="custom",
        global_preface="",
        body_sections=(SectionSpec(id="my_advocacy", title="X", brief="x", voice="any"),),
        synthesis_sections=(),
    )

    report = validate_sections(
        section_files={"my_advocacy": _PROSE_WITH_FIRST_PERSON},
        facts={},
        template=template,
    )

    first_person = [f for f in report.failures if f.failure_type == "first_person_voice"]
    assert first_person == []


def test_template_section_with_voice_third_person_only_is_gated() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    template = TemplateSpec(
        name="custom",
        global_preface="",
        body_sections=(
            SectionSpec(
                id="my_neutral_section",
                title="X",
                brief="x",
                voice="third_person_only",
            ),
        ),
        synthesis_sections=(),
    )

    report = validate_sections(
        section_files={"my_neutral_section": _PROSE_WITH_FIRST_PERSON},
        facts={},
        template=template,
    )

    first_person = [f for f in report.failures if f.failure_type == "first_person_voice"]
    assert len(first_person) == 1
    assert first_person[0].section_id == "my_neutral_section"


def test_default_template_investment_recommendation_has_third_person_voice() -> None:
    from openlia.reports.frameworks.loaders.stock_initiation import (
        load_stock_initiation_template,
    )

    spec = load_stock_initiation_template()
    section = spec.section_by_id("investment_recommendation")

    assert section is not None
    assert section.voice == "third_person_only"
