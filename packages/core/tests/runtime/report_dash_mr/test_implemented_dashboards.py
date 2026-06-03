"""The engine's implemented-dashboard set is the single source of truth
for which MR dashboards can actually be generated. When a new dashboard is
added to ``PAYLOAD_MODEL_BY_SLUG``, this test will fail and remind the
implementer to update the set (and the frontend's hardcoded mirror)."""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    EnabledConnectors,
    RunRequest,
    implemented_dashboard_slugs,
)
from openlia.llm.runtime.report_dash_mr.prompts import build_system_prompt
from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
)


def test_implemented_dashboard_slugs() -> None:
    assert implemented_dashboard_slugs() == frozenset(
        {"debt_cycle", "world_order", "four_seasons", "all_weather", "five_forces", "summary"}
    )


def test_every_classifier_has_a_payload_model() -> None:
    assert set(CLASSIFY_TOOL_BY_SLUG) <= set(PAYLOAD_MODEL_BY_SLUG)


def test_build_system_prompt_rejects_unknown_slug() -> None:
    request = RunRequest(
        dashboard_slug="nonexistent",
        subject="Nonexistent",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(),
    )
    with pytest.raises(ValueError, match="no prompt spec for dashboard 'nonexistent'"):
        build_system_prompt(request)


def test_all_weather_exposes_both_classify_and_stress_tools() -> None:
    from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
    )

    builders = CLASSIFY_TOOL_BY_SLUG["all_weather"]
    names = {b().descriptor.name for b in builders}
    assert names == {"classify_all_weather", "simulate_all_weather_stress"}


def test_four_seasons_exposes_both_classify_and_markov_tools() -> None:
    from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
    )

    builders = CLASSIFY_TOOL_BY_SLUG["four_seasons"]
    names = {b().descriptor.name for b in builders}
    assert names == {"classify_four_seasons", "markov_four_seasons"}


def test_five_forces_exposes_both_classify_and_network_tools() -> None:
    from openlia.llm.runtime.report_dash_mr.tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
    )

    builders = CLASSIFY_TOOL_BY_SLUG["five_forces"]
    names = {b().descriptor.name for b in builders}
    assert names == {"classify_five_forces", "analyze_five_forces_network"}
