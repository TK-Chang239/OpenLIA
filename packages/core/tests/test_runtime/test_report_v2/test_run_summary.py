from __future__ import annotations

from openlia.llm.runtime.report_v2.rendering.run_summary_renderer import (
    render_run_summary,
)
from openlia.llm.runtime.report_v2.schemas.run_summary import (
    RunSummary,
    TaskOutcome,
)


def _base_summary(**kwargs) -> RunSummary:
    defaults = dict(
        engine_version="2.2",
        template_id="nvda_equity",
        template_name="NVDA Equity Report",
        composer_inputs={"ticker": "NVDA"},
        outcomes=[],
        unsupported_requests_dismissed=[],
        unsupported_requests_slipped=[],
        total_duration_ms=1500,
        total_token_cost=None,
        cache_stats={},
    )
    defaults.update(kwargs)
    return RunSummary(**defaults)


def test_run_summary_html_has_all_statuses_visible():
    rs = _base_summary(
        outcomes=[
            TaskOutcome(task_type="research_strand", task_name="gather_financials", status="OK"),
            TaskOutcome(
                task_type="section_draft",
                task_name="draft_valuation",
                status="DEGRADED",
                notes="partial",
            ),
            TaskOutcome(task_type="verification", task_name="verify_eps", status="SKIPPED"),
        ]
    )
    html = render_run_summary(rs)
    assert "OK" in html
    assert "DEGRADED" in html
    assert "SKIPPED" in html
    assert "NVDA" in html
    assert "2.2" in html


def test_run_summary_lists_unsupported_dismissed_and_slipped():
    rs = _base_summary(
        unsupported_requests_dismissed=["extra_passes"],
        unsupported_requests_slipped=["review_loops"],
    )
    html = render_run_summary(rs)
    assert "extra_passes" in html
    assert "review_loops" in html


def test_run_summary_includes_cache_stats():
    rs = _base_summary(
        cache_stats={"transcripts": {"hits": 4, "misses": 1}},
    )
    html = render_run_summary(rs)
    assert "transcripts" in html.lower()
    assert "4" in html


def test_status_color_classes_applied():
    rs = _base_summary(
        outcomes=[
            TaskOutcome(task_type="research_strand", task_name="t1", status="OK"),
            TaskOutcome(task_type="section_draft", task_name="t2", status="DEGRADED"),
            TaskOutcome(task_type="verification", task_name="t3", status="SKIPPED"),
            TaskOutcome(task_type="output_render", task_name="t4", status="FAILED"),
        ]
    )
    html = render_run_summary(rs)
    assert 'class="status-ok"' in html
    assert 'class="status-degraded"' in html
    assert 'class="status-skipped"' in html
    assert 'class="status-failed"' in html


def test_render_handles_empty_dismissed_and_slipped_lists():
    rs = _base_summary(
        unsupported_requests_dismissed=[],
        unsupported_requests_slipped=[],
    )
    html = render_run_summary(rs)
    assert html.count("(none)") >= 2


def test_html_escapes_user_strings_to_prevent_xss():
    rs = _base_summary(
        composer_inputs={"ticker": "<script>alert(1)</script>"},
    )
    html = render_run_summary(rs)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
