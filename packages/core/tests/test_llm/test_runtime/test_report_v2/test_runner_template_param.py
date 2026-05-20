"""Tests for the runner's new optional `template` parameter (PR 1).

PR 1 contract: runner accepts an optional `template: TemplateSpec | None` and
exposes it on the instance for downstream PRs to consume. When None, the runner
resolves the template from `default_registry.get(report_type)`. No runtime
behavior changes in PR 1 — this slice only proves the parameter is plumbed.
"""

from __future__ import annotations

import pytest


def _make_runner(**overrides):
    from openlia.llm.runtime.report_v2.runner import WavedReportRunner

    defaults = dict(
        report_type="stock_initiation",
        ticker="AAPL",
        dispatcher=object(),
        websearch=object(),
        preflight_provider=object(),
        body_writer=object(),
        synthesis_writer=object(),
    )
    defaults.update(overrides)
    return WavedReportRunner(**defaults)


def test_runner_resolves_template_from_registry_when_none_provided() -> None:
    import openlia.reports.frameworks.loaders  # noqa: F401  ensure registration
    from openlia.reports.frameworks.template_spec import TemplateSpec

    runner = _make_runner(template=None)

    assert isinstance(runner.template, TemplateSpec)
    assert runner.template.name == "stock_initiation"


def test_runner_uses_explicit_template_when_provided() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    custom = TemplateSpec(
        name="stock_initiation",
        global_preface="custom preface",
        body_sections=(SectionSpec(id="company_overview", title="X", brief="x"),),
        synthesis_sections=(SectionSpec(id="cover", title="Cover", brief="c"),),
    )

    runner = _make_runner(template=custom)

    assert runner.template is custom
    assert runner.template.global_preface == "custom preface"


def test_runner_raises_when_report_type_unknown_and_no_template() -> None:
    from openlia.reports.frameworks.registry import UnknownTemplateError

    with pytest.raises((UnknownTemplateError, ValueError)):
        _make_runner(report_type="not_a_real_template", template=None)
