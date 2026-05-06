"""Tests for the per-(user, department) report tool cache."""

from __future__ import annotations

from datetime import date

from openlia.llm.types import ToolSchema
from openlia_server.services.report_tool_cache import ReportToolCache
from sqlalchemy.orm import Session

WARMUP_RUNS = 3


def _tool(name: str) -> ToolSchema:
    return ToolSchema(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {}},
    )


def _run(idx: int) -> tuple[str, date]:
    return f"r_{idx}", date(2026, 5, idx)


def test_warmup_run_returns_full_inventory(db_session: Session, seeded_user) -> None:
    cache = ReportToolCache(db_session)
    full = [_tool("eodhd_news"), _tool("firecrawl_search"), _tool("fmp_quote")]
    run_id, run_date = _run(1)

    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=run_id,
        run_date=run_date,
    )
    selected = cache.tools_for(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert {t.name for t in selected} == {"eodhd_news", "firecrawl_search", "fmp_quote"}


def test_after_warmup_only_tools_used_on_three_distinct_days_are_kept(
    db_session: Session, seeded_user
) -> None:
    cache = ReportToolCache(db_session)
    full = [_tool("eodhd_news"), _tool("firecrawl_search"), _tool("fmp_quote")]

    # Three warm-up runs. eodhd_news called successfully on each distinct
    # run-day; the others get one call each.
    for idx in range(1, WARMUP_RUNS + 1):
        run_id, run_date = _run(idx)
        cache.note_run_started(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=run_id,
            run_date=run_date,
        )
        cache.record_tool_call(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=run_id,
            run_date=run_date,
            tool_name="eodhd_news",
            success=True,
        )
        if idx == 1:
            cache.record_tool_call(
                user_id=seeded_user.id,
                department_id="morning_briefing",
                run_id=run_id,
                run_date=run_date,
                tool_name="firecrawl_search",
                success=True,
            )
        if idx == 2:
            cache.record_tool_call(
                user_id=seeded_user.id,
                department_id="morning_briefing",
                run_id=run_id,
                run_date=run_date,
                tool_name="fmp_quote",
                success=True,
            )

    # Fourth run (post warm-up). eodhd_news qualifies (3 distinct days);
    # the others don't (each only used on 1 day).
    run_id, run_date = _run(4)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=run_id,
        run_date=run_date,
    )
    selected = cache.tools_for(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert {t.name for t in selected} == {"eodhd_news"}


def test_failed_calls_do_not_count_toward_promotion(db_session: Session, seeded_user) -> None:
    cache = ReportToolCache(db_session)
    full = [_tool("flaky_tool")]
    for idx in range(1, WARMUP_RUNS + 1):
        run_id, run_date = _run(idx)
        cache.note_run_started(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=run_id,
            run_date=run_date,
        )
        cache.record_tool_call(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=run_id,
            run_date=run_date,
            tool_name="flaky_tool",
            success=False,
        )
    run_id, run_date = _run(4)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=run_id,
        run_date=run_date,
    )
    selected = cache.tools_for(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert selected == []


def test_per_run_dedupe_collapses_repeated_calls_in_same_run(
    db_session: Session, seeded_user
) -> None:
    cache = ReportToolCache(db_session)
    full = [_tool("eodhd_news")]
    # Single warm-up run that calls the tool 5 times. Should count as
    # one day-use, not five — so after warm-up the tool fails to qualify
    # on the 3-distinct-day rule.
    run_id, run_date = _run(1)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=run_id,
        run_date=run_date,
    )
    for _ in range(5):
        cache.record_tool_call(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=run_id,
            run_date=run_date,
            tool_name="eodhd_news",
            success=True,
        )
    # Two more warm-up runs, no calls.
    for idx in (2, 3):
        rid, rd = _run(idx)
        cache.note_run_started(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=rid,
            run_date=rd,
        )
    rid, rd = _run(4)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=rid,
        run_date=rd,
    )
    selected = cache.tools_for(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert selected == []


def test_demotion_when_tool_unused_for_five_distinct_run_days(
    db_session: Session, seeded_user
) -> None:
    cache = ReportToolCache(db_session)
    full = [_tool("eodhd_news"), _tool("old_tool")]

    # Days 1-3: both tools used successfully each day.
    for idx in (1, 2, 3):
        rid, rd = _run(idx)
        cache.note_run_started(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=rid,
            run_date=rd,
        )
        for tool in ("eodhd_news", "old_tool"):
            cache.record_tool_call(
                user_id=seeded_user.id,
                department_id="morning_briefing",
                run_id=rid,
                run_date=rd,
                tool_name=tool,
                success=True,
            )
    # Days 4-8: only eodhd_news used. After 5 distinct days without
    # old_tool, it should drop out of the cache.
    for idx in (4, 5, 6, 7, 8):
        rid, rd = _run(idx)
        cache.note_run_started(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=rid,
            run_date=rd,
        )
        cache.record_tool_call(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=rid,
            run_date=rd,
            tool_name="eodhd_news",
            success=True,
        )

    # Day 9: read the cache.
    rid, rd = _run(9)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=rid,
        run_date=rd,
    )
    selected = cache.tools_for(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert {t.name for t in selected} == {"eodhd_news"}


def test_cache_isolation_per_user_and_department(
    db_session: Session, seeded_user, other_user
) -> None:
    cache = ReportToolCache(db_session)
    full = [_tool("eodhd_news"), _tool("fmp_quote")]

    # User 1 uses eodhd_news 3 days for MB. User 2 has no history.
    for idx in (1, 2, 3):
        rid, rd = _run(idx)
        cache.note_run_started(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=rid,
            run_date=rd,
        )
        cache.record_tool_call(
            user_id=seeded_user.id,
            department_id="morning_briefing",
            run_id=rid,
            run_date=rd,
            tool_name="eodhd_news",
            success=True,
        )
    # User 2 starts a run — should be in warm-up, see full inventory.
    rid, rd = _run(4)
    cache.note_run_started(
        user_id=other_user.id,
        department_id="morning_briefing",
        run_id=rid,
        run_date=rd,
    )
    selected_other = cache.tools_for(
        user_id=other_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert {t.name for t in selected_other} == {"eodhd_news", "fmp_quote"}

    # User 1 also runs — past warm-up, only eodhd_news.
    rid, rd = _run(5)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        run_id=rid,
        run_date=rd,
    )
    selected_seeded = cache.tools_for(
        user_id=seeded_user.id,
        department_id="morning_briefing",
        full_inventory=full,
    )
    assert {t.name for t in selected_seeded} == {"eodhd_news"}

    # MB usage should not bleed into Equity Research for the same user.
    rid, rd = _run(6)
    cache.note_run_started(
        user_id=seeded_user.id,
        department_id="equity_research",
        run_id=rid,
        run_date=rd,
    )
    selected_er = cache.tools_for(
        user_id=seeded_user.id,
        department_id="equity_research",
        full_inventory=full,
    )
    assert {t.name for t in selected_er} == {"eodhd_news", "fmp_quote"}
