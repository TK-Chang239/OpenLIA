import pytest
from openlia.llm.runtime.report_mb.schemas import (
    BriefingContext,
    EnabledConnectors,
    RunRequest,
)
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec
from pydantic import ValidationError


def _template() -> TemplateSpec:
    return TemplateSpec(
        template_id="mb_default",
        name="Morning Briefing",
        shape_description="Recurring market briefing",
        ticker_anchored=False,
        default_length="normal",
        sections=[SectionSpec(id="overnight", title="Overnight", intent="What moved")],
    )


def test_enabled_connectors_defaults():
    c = EnabledConnectors()
    assert c.provider_ids == frozenset()
    assert c.eodhd is False
    assert c.web_search is False


def test_briefing_context_minimal():
    ctx = BriefingContext(run_date="2026-06-02")
    assert ctx.run_date == "2026-06-02"
    assert ctx.schedule_label is None
    assert ctx.time_label is None
    assert ctx.timezone is None


def test_briefing_context_with_schedule_label():
    ctx = BriefingContext(run_date="2026-06-02", schedule_label="Pre-market briefing")
    assert ctx.schedule_label == "Pre-market briefing"


def test_run_request_carries_briefing_context():
    req = RunRequest(
        subject="Morning Briefing - 2026-06-02",
        template=_template(),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(web_search=True),
        briefing_context=BriefingContext(run_date="2026-06-02"),
    )
    assert req.subject == "Morning Briefing - 2026-06-02"
    assert req.briefing_context.run_date == "2026-06-02"
    assert req.enabled_connectors.web_search is True


def test_run_request_has_no_trigger_context():
    req = RunRequest(
        subject="Morning Briefing - 2026-06-02",
        template=_template(),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )
    assert not hasattr(req, "trigger_context")
    assert req.briefing_context is None


def test_run_request_rejects_empty_subject():
    with pytest.raises(ValidationError):
        RunRequest(
            subject="",
            template=_template(),
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
        )
