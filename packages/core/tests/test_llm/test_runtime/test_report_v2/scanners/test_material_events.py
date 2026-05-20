"""Tests for the material-events scanner (WS3 Part B)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from openlia.llm.runtime.report_v2.scanners.material_events import (
    MaterialEvent,
    MaterialEventError,
    MaterialEventScanner,
    scan_manifest,
)
from openlia.llm.runtime.report_v2.types import ManifestEntry


def _news_entry(
    *,
    entry_id: int = 1,
    identifier: str = "financial_news/WOLF.US",
    articles: list[dict[str, Any]],
) -> ManifestEntry:
    return ManifestEntry(
        id=entry_id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=articles,
        retrieved_at="2026-05-19T12:00:00Z",
    )


def _article(
    *,
    title: str,
    content: str = "",
    article_date: str = "2025-06-30",
) -> dict[str, Any]:
    return {"date": article_date, "title": title, "content": content}


# ---------------------------------------------------------------------------
# Positive fixtures — one per event class
# ---------------------------------------------------------------------------


def test_chapter_11_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                content="Wolfspeed announced it has filed a voluntary petition under Chapter 11.",
                article_date="2025-06-30",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="WOLF")
    classes = [e.event_class for e in events]
    assert "chapter_11" in classes
    chapter_11 = next(e for e in events if e.event_class == "chapter_11")
    assert chapter_11.confidence == "high"
    assert chapter_11.severity == "hard_block"
    assert chapter_11.evidence == [1]
    assert chapter_11.event_date == date(2025, 6, 30)


def test_bankruptcy_emergence_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed emerged from Chapter 11 with fresh-start accounting",
                content="The plan of reorganization became effective today.",
                article_date="2025-09-20",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="WOLF")
    classes = [e.event_class for e in events]
    assert "bankruptcy_emergence" in classes
    emergence = next(e for e in events if e.event_class == "bankruptcy_emergence")
    assert emergence.severity == "hard_block"
    assert emergence.confidence == "high"


def test_going_private_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME announces agreement to be taken private at $50/share",
                content="ACME entered into a take-private agreement.",
                article_date="2026-03-01",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert any(e.event_class == "going_private" for e in events)
    gp = next(e for e in events if e.event_class == "going_private")
    assert gp.severity == "hard_block"


def test_ma_target_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME enters definitive merger agreement with BigCo",
                content="ACME has agreed to be acquired by BigCo for cash.",
                article_date="2026-02-15",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert any(e.event_class == "ma_target" for e in events)
    ma = next(e for e in events if e.event_class == "ma_target")
    assert ma.severity == "warning_banner"


def test_delisting_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME removed from listing on NASDAQ",
                content="ACME has been delisted after failing minimum bid price.",
                article_date="2026-01-10",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert any(e.event_class == "delisting" for e in events)
    de = next(e for e in events if e.event_class == "delisting")
    assert de.severity == "hard_block"


def test_stock_split_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME announces 10-for-1 forward stock split",
                content="The split will be effective June 1, 2026.",
                article_date="2026-04-01",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert any(e.event_class == "stock_split" for e in events)
    sp = next(e for e in events if e.event_class == "stock_split")
    assert sp.severity == "warning_banner"


def test_restatement_positive() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME announces restatement of previously issued financial statements",
                content="Non-reliance on previously issued financials disclosed via 8-K Item 4.02.",
                article_date="2026-03-15",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert any(e.event_class == "restatement" for e in events)
    rs = next(e for e in events if e.event_class == "restatement")
    assert rs.severity == "hard_block"


# ---------------------------------------------------------------------------
# Negative fixtures — unrelated content
# ---------------------------------------------------------------------------


def test_unrelated_news_returns_empty() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME reports record quarterly revenue",
                content="ACME beat consensus estimates and raised full-year guidance.",
                article_date="2026-04-30",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert events == []


def test_negation_guard_suppresses_chapter_11() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME avoided bankruptcy after capital raise",
                content="The company avoided bankruptcy by securing new financing.",
                article_date="2026-01-01",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert all(e.event_class != "chapter_11" for e in events)


def test_terminated_ma_suppressed() -> None:
    entry = _news_entry(
        articles=[
            _article(
                title="ACME and BigCo terminated merger agreement",
                content="The proposed merger has been called off.",
                article_date="2026-02-20",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="ACME")
    assert all(e.event_class != "ma_target" for e in events)


# ---------------------------------------------------------------------------
# WOLF-style hard-block scenarios
# ---------------------------------------------------------------------------


def test_wolf_chapter_11_after_data_as_of_is_hard_block() -> None:
    """The canonical WOLF failure mode — Chapter 11 filing dated AFTER the
    fundamentals data_as_of must surface as hard_block with high confidence."""
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                content="Wolfspeed filed for bankruptcy protection.",
                article_date="2025-06-30",
            )
        ]
    )
    events = scan_manifest(
        [entry],
        subject_ticker="WOLF",
        as_of_date="2025-05-01",  # fundamentals predate the filing
    )
    hard = [e for e in events if e.severity == "hard_block"]
    assert len(hard) >= 1
    chapter_11 = next(e for e in hard if e.event_class == "chapter_11")
    assert chapter_11.confidence == "high"


def test_wolf_chapter_11_before_data_as_of_does_not_block() -> None:
    """Same event, dated BEFORE the data_as_of — the scanner still surfaces
    it (so body sections can cover it) but does NOT escalate to hard_block."""
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                content="Wolfspeed filed for bankruptcy protection.",
                article_date="2025-06-30",
            )
        ]
    )
    events = scan_manifest(
        [entry],
        subject_ticker="WOLF",
        as_of_date="2026-01-01",  # fundamentals are newer than the filing
    )
    classes = [e.event_class for e in events]
    assert "chapter_11" in classes
    assert all(e.severity == "informational" for e in events if e.event_class == "chapter_11")


# ---------------------------------------------------------------------------
# Override + confidence behaviour
# ---------------------------------------------------------------------------


def test_override_flag_bypasses_hard_block() -> None:
    """The override is enforced by the runner; verify the exception carries
    the offending events on `.events` for diagnostics."""
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                content="Filed for bankruptcy.",
                article_date="2025-06-30",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="WOLF", as_of_date="2025-05-01")
    hard = [e for e in events if e.severity == "hard_block"]
    assert hard
    err = MaterialEventError(hard)
    assert err.events == hard
    assert "chapter_11" in str(err)


def test_confidence_downgrades_when_company_name_missing() -> None:
    """A Chapter 11 mention without the subject ticker / company name in the
    article downgrades from high to medium."""
    entry = _news_entry(
        articles=[
            _article(
                title="A semiconductor company files voluntary Chapter 11 petition",
                content="An unnamed semiconductor company filed under Chapter 11.",
                article_date="2025-06-30",
            )
        ]
    )
    events = scan_manifest([entry], subject_ticker="WOLF")
    chapter_11 = next(e for e in events if e.event_class == "chapter_11")
    # Strong pattern but no name match → medium confidence.
    assert chapter_11.confidence == "medium"


def test_no_news_entries_returns_empty() -> None:
    """When the manifest carries no news entries at all, the scanner returns
    no detections — this is the documented behaviour when news isn't packed
    yet."""
    fundamentals = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/WOLF.US",
        raw_payload={"General": {"Code": "WOLF"}},
        retrieved_at="2026-05-19T12:00:00Z",
    )
    events = scan_manifest([fundamentals], subject_ticker="WOLF")
    assert events == []


def test_scanner_class_round_trip() -> None:
    scanner = MaterialEventScanner(subject_ticker="WOLF", as_of_date=date(2025, 5, 1))
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                article_date="2025-06-30",
            )
        ]
    )
    events = scanner.scan([entry])
    assert any(e.event_class == "chapter_11" and e.severity == "hard_block" for e in events)


def test_material_event_dataclass_shape() -> None:
    e = MaterialEvent(
        event_class="chapter_11",
        event_date=date(2025, 6, 30),
        confidence="high",
        severity="hard_block",
        evidence=[1, 2],
        description="chapter_11: Wolfspeed files Chapter 11",
    )
    assert e.event_class == "chapter_11"
    assert e.severity == "hard_block"
    assert e.evidence == [1, 2]


# ---------------------------------------------------------------------------
# Multiple manifest entries — evidence aggregation
# ---------------------------------------------------------------------------


def test_multiple_news_entries_each_contribute_evidence() -> None:
    e1 = _news_entry(
        entry_id=1,
        articles=[
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                article_date="2025-06-30",
            )
        ],
    )
    e2 = _news_entry(
        entry_id=2,
        identifier="financial_news/WOLF.US?offset=50",
        articles=[
            _article(
                title="Wolfspeed bankruptcy filing details",
                content="Wolfspeed files for bankruptcy protection.",
                article_date="2025-07-01",
            )
        ],
    )
    events = scan_manifest([e1, e2], subject_ticker="WOLF")
    chapter_11_events = [e for e in events if e.event_class == "chapter_11"]
    # Two separate articles → two MaterialEvent rows (one per article).
    assert len(chapter_11_events) == 2
    assert {e.evidence[0] for e in chapter_11_events} == {1, 2}


# ---------------------------------------------------------------------------
# Synthetic WOLF-like extractor smoke (~30s budget)
# ---------------------------------------------------------------------------


def test_synthetic_wolf_smoke() -> None:
    """End-to-end-ish smoke: feed a small WOLF-like news payload through the
    scanner and confirm a hard_block Chapter 11 MaterialEvent comes out."""
    entry = _news_entry(
        articles=[
            _article(
                title="Wolfspeed announces strategic review",
                content="The company announced a strategic review of options.",
                article_date="2025-05-15",
            ),
            _article(
                title="Wolfspeed files voluntary Chapter 11 petition",
                content=(
                    "Wolfspeed, Inc. (NYSE: WOLF) today announced that it has "
                    "filed a voluntary petition for relief under Chapter 11 of "
                    "the U.S. Bankruptcy Code."
                ),
                article_date="2025-06-30",
            ),
            _article(
                title="Wolfspeed emerged from Chapter 11",
                content=(
                    "Wolfspeed today announced that it has emerged from "
                    "Chapter 11 with fresh-start accounting applied."
                ),
                article_date="2025-09-20",
            ),
        ]
    )
    events = scan_manifest(
        [entry],
        subject_ticker="WOLF",
        as_of_date="2025-05-01",  # data predates both events
    )
    hard = [e for e in events if e.severity == "hard_block"]
    assert any(e.event_class == "chapter_11" for e in hard)
    assert any(e.event_class == "bankruptcy_emergence" for e in hard)
    # Confidence is high because "Wolfspeed" appears in every article body.
    chapter_11 = next(e for e in hard if e.event_class == "chapter_11")
    assert chapter_11.confidence == "high"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_date_field_still_detects() -> None:
    """An article with no date should still surface the event with
    event_date=None — the runner treats undated events as not-yet-classified
    against the freshness boundary."""
    entry = _news_entry(
        articles=[
            {
                "title": "Wolfspeed files voluntary Chapter 11 petition",
                "content": "Wolfspeed filed for bankruptcy.",
            }
        ]
    )
    events = scan_manifest([entry], subject_ticker="WOLF", as_of_date="2025-05-01")
    chapter_11 = next(e for e in events if e.event_class == "chapter_11")
    assert chapter_11.event_date is None
    # With no event_date we cannot demote; natural severity applies.
    assert chapter_11.severity == "hard_block"


def test_envelope_payload_with_items_key() -> None:
    """Some news providers wrap articles in {"items": [...]}; scanner unwraps."""
    entry = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="financial_news/WOLF.US",
        raw_payload={
            "items": [
                {
                    "title": "Wolfspeed files voluntary Chapter 11 petition",
                    "content": "Bankruptcy filing.",
                    "date": "2025-06-30",
                }
            ]
        },
        retrieved_at="2026-05-19T12:00:00Z",
    )
    events = scan_manifest([entry], subject_ticker="WOLF")
    assert any(e.event_class == "chapter_11" for e in events)


def test_non_news_entries_ignored() -> None:
    """Manifest entries that aren't news (fundamentals, prices) are skipped."""
    fundamentals = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/WOLF.US",
        # Even if Chapter 11 keywords appear in the payload, non-news entries
        # are skipped — only news/EDGAR sources are scanned.
        raw_payload={"Description": "files voluntary Chapter 11 petition"},
        retrieved_at="2026-05-19T12:00:00Z",
    )
    events = scan_manifest([fundamentals], subject_ticker="WOLF")
    assert events == []


@pytest.mark.parametrize(
    "event_class,title",
    [
        ("chapter_11", "ACME files voluntary Chapter 11 petition"),
        ("bankruptcy_emergence", "ACME emerged from Chapter 11"),
        ("going_private", "ACME signs take-private agreement"),
        ("ma_target", "ACME enters definitive merger agreement"),
        ("delisting", "ACME delisted from NYSE"),
        ("stock_split", "ACME announces 3-for-1 forward stock split"),
        (
            "restatement",
            "ACME announces restatement of previously issued financial statements",
        ),
    ],
)
def test_each_class_fires(event_class: str, title: str) -> None:
    entry = _news_entry(articles=[_article(title=title, article_date="2026-04-01")])
    events = scan_manifest([entry], subject_ticker="ACME")
    assert any(e.event_class == event_class for e in events), (
        f"class {event_class} missing from {[e.event_class for e in events]}"
    )
