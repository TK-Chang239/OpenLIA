from __future__ import annotations

import pytest

from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.dashboards.base import Dashboard


@pytest.mark.parametrize("slug", list(DASHBOARDS.keys()))
def test_each_dashboard_honours_protocol(slug: str) -> None:
    d = DASHBOARDS[slug]
    assert isinstance(d, Dashboard)
    assert d.slug == slug
    assert isinstance(d.display_name, str) and d.display_name
    assert isinstance(d.T1_REQUIREMENTS, tuple)
    assert isinstance(d.T2_FORMULAS, dict)
    assert hasattr(d, "T4_PROMPT_KEY")
    assert callable(d.T3_compute)
    assert callable(d.T5_smart_mode_adjustments)


def test_t3_compute_tolerates_empty() -> None:
    for slug, d in DASHBOARDS.items():
        result = d.T3_compute(metrics={}, portfolio=None)
        assert isinstance(result, dict), slug


def test_t5_smart_mode_is_pure() -> None:
    for slug, d in DASHBOARDS.items():
        base = {"foo": 1.0}
        out = d.T5_smart_mode_adjustments(base_thresholds=base, context={"smart_mode": False})
        assert out == base, slug
        assert base == {"foo": 1.0}
