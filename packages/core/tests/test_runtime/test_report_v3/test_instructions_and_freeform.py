"""Instruction-profile injection + freeform (no-template) mode.

Covers the v3 changes that let a run carry free-form analyst
instructions and/or run with no fixed template:

  - build_system_prompt injects an ``# Analyst instructions`` block
    only when instructions are present.
  - build_system_prompt renders the fixed section list for templated
    runs and the freeform directive when the template has no sections.
  - write_section accepts arbitrary section ids in freeform mode but
    still rejects unknown ids in templated mode.
  - finalize blocks a freeform run with zero sections, then succeeds
    once at least one section is written.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    CitationLedger,
    Language,
    ReportLength,
    ReviseContext,
    RunRequest,
    RunWorkspace,
    TemplateSpec,
)
from openlia.llm.runtime.report_v3.prompts import (
    build_revise_system_prompt,
    build_system_prompt,
)
from openlia.llm.runtime.report_v3.tools import build_catalog
from openlia.llm.runtime.report_v3.tools.output_tools import build_output_tools


def _dummy_transport(*_args, **_kwargs):
    raise AssertionError("data transport should not be called in these tests")


def _freeform_template() -> TemplateSpec:
    """Sections-less spec, mirroring the route's freeform construction."""
    return TemplateSpec.model_construct(
        template_id="freeform",
        name="Freeform",
        shape_description="No fixed template.",
        ticker_anchored=False,
        default_length=None,
        sections=[],
    )


def _catalog(template: TemplateSpec) -> tuple[object, CitationLedger]:
    ledger = CitationLedger()
    workspace = RunWorkspace(template=template, ledger=ledger, subject="RKLB.US")
    catalog = build_catalog(
        ledger=ledger,
        workspace=workspace,
        fundamentals=_dummy_transport,
        prices=_dummy_transport,
        news=_dummy_transport,
    )
    return catalog, ledger


def _request(*, template: TemplateSpec, instructions: str | None = None) -> RunRequest:
    return RunRequest(
        subject="RKLB.US",
        template=template,
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        instructions=instructions,
    )


# --- prompt: instructions block ---------------------------------------------


def test_prompt_injects_instructions_block_when_present():
    template = get_builtin(ReportType.INITIATION)
    catalog, _ = _catalog(template)
    marker = "INDUSTRY-WINNER METHODOLOGY MARKER"
    prompt = build_system_prompt(
        request=_request(template=template, instructions=f"{marker}\nLook first."),
        catalog=catalog,
    )
    assert "# Analyst instructions" in prompt
    assert marker in prompt


def test_prompt_omits_instructions_block_when_absent():
    template = get_builtin(ReportType.INITIATION)
    catalog, _ = _catalog(template)
    prompt = build_system_prompt(
        request=_request(template=template, instructions=None), catalog=catalog
    )
    assert "# Analyst instructions" not in prompt


def test_prompt_whitespace_only_instructions_treated_as_absent():
    template = get_builtin(ReportType.INITIATION)
    catalog, _ = _catalog(template)
    prompt = build_system_prompt(
        request=_request(template=template, instructions="   \n\t "), catalog=catalog
    )
    assert "# Analyst instructions" not in prompt


# --- prompt: templated vs freeform structure --------------------------------


def test_prompt_templated_lists_required_sections():
    template = get_builtin(ReportType.INITIATION)
    catalog, _ = _catalog(template)
    prompt = build_system_prompt(request=_request(template=template), catalog=catalog)
    assert "You MUST produce a `write_section` call for every section id" in prompt
    # Real section ids appear in the rendered list.
    assert f"id: {template.sections[0].id}" in prompt


def test_prompt_freeform_emits_design_directive():
    template = _freeform_template()
    catalog, _ = _catalog(template)
    prompt = build_system_prompt(
        request=_request(template=template, instructions="Methodology here."),
        catalog=catalog,
    )
    assert "No fixed section structure is imposed" in prompt
    assert "You MUST produce a `write_section` call for every section id" not in prompt


# --- write_section: freeform vs templated -----------------------------------


def test_write_section_freeform_accepts_arbitrary_id():
    ledger = CitationLedger()
    workspace = RunWorkspace(template=_freeform_template(), ledger=ledger, subject="RKLB.US")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    result = tools["write_section"].execute(
        {"section_id": "my_own_section", "markdown": "Some analysis."}
    )
    assert result.payload["ok"] is True
    assert "my_own_section" in workspace.sections
    # Title derived from the slug when not a template id.
    assert workspace.sections["my_own_section"].title == "My Own Section"


def test_write_section_templated_still_rejects_unknown_id():
    template = get_builtin(ReportType.INITIATION)
    ledger = CitationLedger()
    workspace = RunWorkspace(template=template, ledger=ledger, subject="RKLB.US")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    try:
        tools["write_section"].execute({"section_id": "not_a_section", "markdown": "x"})
    except RuntimeError as exc:
        assert "Unknown section_id" in str(exc)
    else:
        raise AssertionError("expected unknown-section rejection in templated mode")


# --- finalize: freeform empty guard -----------------------------------------


def test_finalize_freeform_blocks_when_no_sections_written():
    ledger = CitationLedger()
    workspace = RunWorkspace(template=_freeform_template(), ledger=ledger, subject="RKLB.US")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    result = tools["finalize"].execute({})
    assert result.payload["ok"] is False
    assert "No sections written" in result.payload["message"]
    assert workspace.finalized is False


def test_finalize_freeform_succeeds_after_one_section():
    ledger = CitationLedger()
    workspace = RunWorkspace(template=_freeform_template(), ledger=ledger, subject="RKLB.US")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    tools["write_section"].execute({"section_id": "overview", "markdown": "An overview."})
    result = tools["finalize"].execute({})
    assert result.payload["ok"] is True
    assert workspace.finalized is True


# --- revise prompt: instructions replayed ------------------------------------


def _revise_ctx() -> ReviseContext:
    return ReviseContext(
        revision_request="Tighten the bull case.",
        prior_sections=[],
        prior_charts=[],
        prior_citations=[],
    )


def test_revise_prompt_injects_instructions_block_when_present():
    template = get_builtin(ReportType.INITIATION)
    catalog, _ = _catalog(template)
    marker = "WINNER METHODOLOGY REVISION MARKER"
    prompt = build_revise_system_prompt(
        request=_request(template=template, instructions=f"{marker}\nStay disciplined."),
        catalog=catalog,
        revise=_revise_ctx(),
    )
    assert "# Analyst instructions" in prompt
    assert marker in prompt


def test_revise_prompt_omits_instructions_block_when_absent():
    template = get_builtin(ReportType.INITIATION)
    catalog, _ = _catalog(template)
    prompt = build_revise_system_prompt(
        request=_request(template=template, instructions=None),
        catalog=catalog,
        revise=_revise_ctx(),
    )
    assert "# Analyst instructions" not in prompt


def test_revise_prompt_freeform_template_renders():
    # A no-template report being revised: empty sections must not break
    # the revise prompt, and the instructions still ride along.
    template = _freeform_template()
    catalog, _ = _catalog(template)
    prompt = build_revise_system_prompt(
        request=_request(template=template, instructions="Methodology."),
        catalog=catalog,
        revise=_revise_ctx(),
    )
    assert "# Analyst instructions" in prompt
    assert "revision request" in prompt.lower()
