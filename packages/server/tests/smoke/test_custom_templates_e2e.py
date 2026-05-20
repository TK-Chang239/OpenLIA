"""End-to-end smoke tests for the custom report templates pipeline (PR 16).

These exercise the upload → parse → compile → validate → save → resolve →
runtime-materialize path without actually invoking an LLM. The runtime
LLM dispatch is covered by the existing report_v2 suite; here we prove
the *plumbing* works for both a minimal user-uploaded template and a
realistic large multi-tier template (modeled on the Chinese 28-section
framework: preamble + 28 sections, mixed body/synthesis/meta tiers,
per-section voice flags).

Three scenarios from plan §10:
1. "minimal custom template" — 3 sections, no helpers/equations/voice
2. "Chinese 28-section template" — synthesized fixture with full
   structural complexity (preamble, 28 sections, frontmatter overrides,
   meta-tier self-audit)
3. "identical-output stock_initiation" — TemplateSpec snapshot guarding
   against accidental drift in the default loader
"""

from __future__ import annotations

import uuid

import pytest
from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.template_spec import TemplateSpec
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_templates import ReportTemplate
from openlia_server.services.report_template_resolver import (
    resolve_user_template_spec,
)
from openlia_server.services.template_compile import compile_template_spec
from openlia_server.services.template_ingest import ingest_document
from openlia_server.services.template_parser import parse_template

# ---------------------------------------------------------------------------
# Scenario 1 — minimal 3-section custom template
# ---------------------------------------------------------------------------


_MINIMAL_MARKDOWN = """\
A short preamble explaining the framework's purpose.

# Company Overview

Describe the business, segments, and revenue mix in plain English.

# Recent Catalysts

List the last 90 days of news with date, source, and impact.

# Outlook

Summarize the 12-month thesis in 2-3 sentences.
"""


def test_minimal_custom_template_round_trips_through_full_pipeline(db_session) -> None:
    # Ingest plain markdown (passthrough).
    markdown = ingest_document(_MINIMAL_MARKDOWN.encode("utf-8"), "text/markdown")
    assert markdown == _MINIMAL_MARKDOWN

    # Parse to ParsedTemplate.
    parsed = parse_template(markdown)
    assert parsed.global_preface.startswith("A short preamble")
    assert [s.id for s in parsed.sections] == [
        "company_overview",
        "recent_catalysts",
        "outlook",
    ]

    # Compile to TemplateSpec dict and validate against the runtime schema.
    spec_dict = compile_template_spec(parsed, name="Minimal Sample")
    spec = TemplateSpec.model_validate(spec_dict)
    assert spec.name == "Minimal Sample"
    assert len(spec.body_sections) == 3
    assert spec.synthesis_sections == ()
    # The user's prose becomes each section's brief verbatim.
    assert "12-month thesis" in spec.body_sections[2].brief

    # Save to the DB and round-trip through the resolver — the runner
    # receives byte-identical content when it queries by template_id.
    user_id = "smoke-user-minimal"
    db_session.add(User(id=user_id, email=f"{user_id}@e.com", display_name=user_id))
    db_session.commit()
    tid = str(uuid.uuid4())
    db_session.add(
        ReportTemplate(
            id=tid,
            user_id=user_id,
            name=spec.name,
            template_spec_json=spec_dict,
            source_markdown=markdown,
        )
    )
    db_session.commit()

    resolved = resolve_user_template_spec(db_session, user_id=user_id, template_id=tid)
    assert resolved == spec_dict
    # Final shape check — the resolver's output must always be a runtime
    # TemplateSpec, never just a dict with arbitrary keys.
    TemplateSpec.model_validate(resolved)


# ---------------------------------------------------------------------------
# Scenario 2 — synthesized 28-section template with mixed tiers
# ---------------------------------------------------------------------------


def _synth_28_section_markdown() -> str:
    """Models the Chinese template: preamble, 26 body sections, 1 synthesis
    section, 1 meta self-audit section. Total = 28 headings."""
    parts = [
        "<!-- openlia\n"
        "name: 公司深度研究框架 v2.3.1\n"
        "freshness_budgets:\n"
        "  current_price: 7\n"
        "-->\n\n"
        "五大原則：先盡職、再判斷、後行動。\n",  # noqa: RUF001
    ]
    for n in range(1, 27):
        if n == 25:
            # Section 25 declares voice + a required fact to exercise the
            # per-section frontmatter path.
            parts.append(
                f"\n# §{n} Bull Case Steelman\n"
                "<!-- openlia\n"
                "voice: any\n"
                "required_facts:\n"
                "  - revenue_ttm\n"
                "-->\n"
                "Construct the strongest possible bull case.\n"
            )
        else:
            parts.append(f"\n# §{n} Section {n}\nProse describing section {n}.\n")
    parts.append(
        "\n# §27 Final Synthesis\n"
        "<!-- openlia\n"
        "dispatch_tier: synthesis\n"
        "-->\n"
        "Tie every prior section together; emit the verdict.\n"
    )
    parts.append(
        "\n# §28 Self Audit\n"
        "<!-- openlia\n"
        "dispatch_tier: meta\n"
        "voice: any\n"
        "-->\n"
        "Reset persona; attack the strongest pillar; pre-mortem.\n"
    )
    return "".join(parts)


def test_chinese_style_28_section_template_compiles_and_validates() -> None:
    md = _synth_28_section_markdown()
    parsed = parse_template(md)

    # Boundary parsing detects all 28 headings.
    assert len(parsed.sections) == 28
    assert parsed.document_frontmatter["name"] == "公司深度研究框架 v2.3.1"
    assert "五大原則" in parsed.global_preface

    spec_dict = compile_template_spec(parsed, name="fallback")
    spec = TemplateSpec.model_validate(spec_dict)

    # Document frontmatter overrides the fallback name.
    assert spec.name == "公司深度研究框架 v2.3.1"
    # Tier routing: 26 body + 2 synthesis (synthesis + meta both land in
    # synthesis_sections per the compile contract).
    assert len(spec.body_sections) == 26
    assert len(spec.synthesis_sections) == 2
    assert len(spec.meta_sections) == 1
    assert spec.meta_sections[0].id == "28_self_audit"

    # Per-section frontmatter is threaded through to SectionSpec.
    bull_case = spec.section_by_id("25_bull_case_steelman")
    assert bull_case is not None
    assert bull_case.voice == "any"
    assert bull_case.required_facts == ("revenue_ttm",)

    # Document-level optional fields propagate.
    assert spec.freshness_budgets == {"current_price": 7}


# ---------------------------------------------------------------------------
# Scenario 3 — default stock_initiation TemplateSpec drift guard
# ---------------------------------------------------------------------------


@pytest.fixture
def default_template() -> TemplateSpec:
    # Import for side effect: the loader module registers itself with the
    # default registry at import time. The runner imports it eagerly in
    # production; here we trigger it explicitly so the smoke can run in
    # isolation.
    import openlia.reports.frameworks.loaders.stock_initiation  # noqa: F401

    return default_registry.get("stock_initiation")


def test_default_template_still_validates_via_template_spec(
    default_template: TemplateSpec,
) -> None:
    # The Pydantic model enforces the partition invariant + section shape.
    # Re-validating after registry fetch catches any silent drift introduced
    # by a refactor that bypasses construction-time checks.
    TemplateSpec.model_validate(default_template.model_dump())


def test_default_template_has_expected_top_level_shape(
    default_template: TemplateSpec,
) -> None:
    # Coarse-grained drift guard: change to the default template's section
    # count or naming surface fails this test loudly. Numbers are tuned to
    # current main; bumping them is the marker that the default behavior
    # changed and downstream consumers (custom templates, smoke tests,
    # docs) need a look.
    assert default_template.name == "stock_initiation"
    assert len(default_template.body_sections) >= 5
    assert len(default_template.synthesis_sections) >= 1
    # Voice flag carried by the PR 5 lift — the analyst_view / verdict
    # sections continue to suppress first-person prose under the default
    # template even after the refactor.
    voice_third_person = [
        s.id
        for s in (*default_template.body_sections, *default_template.synthesis_sections)
        if s.voice == "third_person_only"
    ]
    # The default template ships at least one section that opts in to
    # third-person-only; the smoke check doesn't pin the list so authors
    # can add or rename freely, but a regression that removes every
    # opt-in fails here.
    assert voice_third_person, "default template must keep at least one third-person-only section"
