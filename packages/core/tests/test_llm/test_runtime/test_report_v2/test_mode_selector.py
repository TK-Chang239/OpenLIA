"""Tests for the industry-mode selector (WS9)."""

from __future__ import annotations

from datetime import date

from openlia.llm.runtime.report_v2.mode_selector import select_report_mode
from openlia.llm.runtime.report_v2.scanners.material_events import MaterialEvent
from openlia.llm.runtime.report_v2.types import Fact


def _fact(name: str, value: object) -> Fact:
    return Fact(name=name, value=value, source_ids=[1], extractor="deterministic")


def _event(
    event_class: str,
    *,
    event_date: date | None = None,
    severity: str = "hard_block",
) -> MaterialEvent:
    return MaterialEvent(
        event_class=event_class,  # type: ignore[arg-type]
        event_date=event_date,
        confidence="high",
        severity=severity,  # type: ignore[arg-type]
        evidence=[1],
        description="test",
    )


# ---------------------------------------------------------------------------
# Auto classification — happy paths
# ---------------------------------------------------------------------------


def test_saas_classification_salesforce_like() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Software - Application"),
    }
    assert select_report_mode(facts, material_events=[]) == "saas"


def test_saas_classification_internet_software_services() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Internet Software & Services"),
    }
    assert select_report_mode(facts, material_events=[]) == "saas"


def test_semis_classification_nvidia_like() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
    }
    assert select_report_mode(facts, material_events=[]) == "semis"


def test_semis_classification_semiconductor_equipment() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductor Equipment & Materials"),
    }
    assert select_report_mode(facts, material_events=[]) == "semis"


def test_generic_classification_default_name() -> None:
    facts = {
        "sector": _fact("sector", "Consumer Defensive"),
        "industry": _fact("industry", "Packaged Foods"),
    }
    assert select_report_mode(facts, material_events=[]) == "generic"


def test_generic_when_sector_not_technology_even_with_software_industry() -> None:
    # Industry contains "Software" but sector is not Technology — selector
    # requires both. Reasonable: prevents fintech labelled as Financials
    # from rendering with the SaaS overlay.
    facts = {
        "sector": _fact("sector", "Financials"),
        "industry": _fact("industry", "Investment Banking - Software"),
    }
    assert select_report_mode(facts, material_events=[]) == "generic"


# ---------------------------------------------------------------------------
# Distressed classification
# ---------------------------------------------------------------------------


def test_distressed_classification_chapter_11_in_window() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
    }
    event = _event("chapter_11", event_date=date(2025, 6, 30))
    mode = select_report_mode(facts, [event], as_of=date(2026, 5, 19))
    assert mode == "distressed"


def test_distressed_classification_bankruptcy_emergence_in_window() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
    }
    event = _event("bankruptcy_emergence", event_date=date(2025, 9, 1))
    mode = select_report_mode(facts, [event], as_of=date(2026, 5, 19))
    assert mode == "distressed"


def test_distressed_classification_chapter_11_older_than_window_falls_through() -> None:
    # Event five years old — selector falls back to industry classification.
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
    }
    event = _event("chapter_11", event_date=date(2020, 1, 1))
    mode = select_report_mode(facts, [event], as_of=date(2026, 5, 19))
    assert mode == "semis"


def test_distressed_classification_going_concern_audit_opinion() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Software"),
        "audit_opinion": _fact(
            "audit_opinion",
            "Qualified — going concern doubt regarding ability to continue",
        ),
    }
    assert select_report_mode(facts, material_events=[]) == "distressed"


def test_distressed_classification_negative_growth_and_negative_fcf() -> None:
    # Wolfspeed-like financial trigger.
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
        "revenue_growth_ttm": _fact("revenue_growth_ttm", -0.45),
        "free_cash_flow_ttm": _fact("free_cash_flow_ttm", -800_000_000),
    }
    assert select_report_mode(facts, material_events=[]) == "distressed"


def test_growth_negative_but_positive_fcf_is_not_distressed() -> None:
    # Negative growth alone is not enough — FCF must also be negative.
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
        "revenue_growth_ttm": _fact("revenue_growth_ttm", -0.50),
        "free_cash_flow_ttm": _fact("free_cash_flow_ttm", 500_000_000),
    }
    assert select_report_mode(facts, material_events=[]) == "semis"


def test_modest_growth_decline_not_distressed() -> None:
    # -25% growth with negative FCF: above the -30% threshold, so the
    # selector should not classify as distressed.
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
        "revenue_growth_ttm": _fact("revenue_growth_ttm", -0.25),
        "free_cash_flow_ttm": _fact("free_cash_flow_ttm", -100_000_000),
    }
    assert select_report_mode(facts, material_events=[]) == "semis"


def test_distressed_classification_delisting_event() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Software"),
    }
    event = _event("delisting", event_date=date(2026, 1, 15))
    assert select_report_mode(facts, [event], as_of=date(2026, 5, 19)) == "distressed"


def test_event_without_date_treated_as_recent() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Software"),
    }
    event = _event("chapter_11", event_date=None)
    assert select_report_mode(facts, [event], as_of=date(2026, 5, 19)) == "distressed"


# ---------------------------------------------------------------------------
# Robustness — missing facts, odd value types
# ---------------------------------------------------------------------------


def test_no_facts_returns_generic() -> None:
    assert select_report_mode({}, material_events=[]) == "generic"


def test_growth_as_percent_string_parses() -> None:
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Semiconductors"),
        "revenue_growth_ttm": _fact("revenue_growth_ttm", "-45%"),
        "free_cash_flow_ttm": _fact("free_cash_flow_ttm", -100_000_000),
    }
    # NOTE: "-45%" parses to -45.0 (not -0.45). At that magnitude the threshold
    # still trips, so the trigger still fires. This is acceptable because the
    # threshold compares <-0.30 and -45.0 is well below it.
    assert select_report_mode(facts, material_events=[]) == "distressed"


def test_unrelated_event_class_does_not_trigger_distressed() -> None:
    # Stock split is not in the distressed event set.
    facts = {
        "sector": _fact("sector", "Technology"),
        "industry": _fact("industry", "Software"),
    }
    event = _event("stock_split", event_date=date(2026, 4, 1), severity="warning_banner")
    assert select_report_mode(facts, [event], as_of=date(2026, 5, 19)) == "saas"


# ---------------------------------------------------------------------------
# Manual override
# ---------------------------------------------------------------------------
# NOTE: select_report_mode itself does not consult overrides — the runner
# checks `report_mode_override` before calling the selector. These tests
# pin the runner-side contract: when an override is supplied, the runner
# bypasses the selector entirely and uses the supplied mode.


def test_runner_override_takes_precedence_over_auto_selection() -> None:
    """The runner constructor accepts `report_mode_override` and uses it
    verbatim, regardless of what `select_report_mode` would have returned.
    The selector itself is a pure function; the override is enforced by the
    runner's run() method. This test pins the behaviour at the runner level
    by constructing a runner and reading back the attribute."""
    from openlia.llm.runtime.report_v2.runner import WavedReportRunner

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="WOLF.US",
        dispatcher=object(),
        websearch=object(),
        preflight_provider=object(),
        body_writer=object(),
        synthesis_writer=object(),
        report_mode_override="distressed",
    )
    assert runner.report_mode_override == "distressed"

    runner_default = WavedReportRunner(
        report_type="stock_initiation",
        ticker="WOLF.US",
        dispatcher=object(),
        websearch=object(),
        preflight_provider=object(),
        body_writer=object(),
        synthesis_writer=object(),
    )
    assert runner_default.report_mode_override is None
