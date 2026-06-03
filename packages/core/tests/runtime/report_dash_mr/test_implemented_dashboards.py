"""The engine's implemented-dashboard set is the single source of truth
for which MR dashboards can actually be generated. When a new dashboard is
added to ``PAYLOAD_MODEL_BY_SLUG``, this test will fail and remind the
implementer to update the set (and the frontend's hardcoded mirror)."""

from openlia.llm.runtime.report_dash_mr import implemented_dashboard_slugs


def test_implemented_dashboard_slugs_is_debt_cycle_only() -> None:
    assert implemented_dashboard_slugs() == frozenset({"debt_cycle"})
