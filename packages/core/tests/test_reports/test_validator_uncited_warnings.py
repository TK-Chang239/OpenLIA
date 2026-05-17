"""Phase 5d: validator warns when concrete-claim slots ship without
source_ids.

Warn-mode does not fail validation — the report still ships. The
warning is collected so the runner can surface it to the dev panel
and (in Phase 6) optionally promote to a hard error in strict mode.
"""

from __future__ import annotations

from openlia.reports.schema import (
    Cover,
    KeyFindingBlock,
    Metric,
    MetricCardsBlock,
    PullQuoteBlock,
    QuoteBlock,
    ReportSchema,
    Section,
)
from openlia.reports.validator import (
    ReportValidationWarning,
    find_uncited_concrete_claims,
)


def _make_schema(*blocks) -> ReportSchema:
    """Build a minimal valid ReportSchema with the given blocks in
    section 'overview'. Citations list is left empty for these tests."""
    return ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at="2026-05-14T00:00:00+00:00",
        cover=Cover(title="X", subtitle="y", tagline="z"),
        sections=[
            Section(
                id="overview",
                title="Overview",
                blocks=list(blocks),
            )
        ],
    )


def test_metric_without_source_ids_emits_warning() -> None:
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[Metric(label="Revenue", value="$95.4B")],
        )
    )
    warnings = find_uncited_concrete_claims(schema)
    assert len(warnings) == 1
    w = warnings[0]
    assert isinstance(w, ReportValidationWarning)
    assert w.kind == "uncited_concrete_claim"
    assert w.slot == "metric"
    assert "Revenue" in w.message
    assert "overview" in w.path


def test_metric_with_source_ids_emits_no_warning() -> None:
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[Metric(label="Revenue", value="$95.4B", source_ids=["c1"])],
        )
    )
    assert find_uncited_concrete_claims(schema) == []


def test_key_finding_without_source_ids_emits_warning() -> None:
    schema = _make_schema(KeyFindingBlock(type="key_finding", content="Margins inflected upward."))
    warnings = find_uncited_concrete_claims(schema)
    assert len(warnings) == 1
    assert warnings[0].slot == "key_finding"


def test_pull_quote_without_source_ids_emits_warning() -> None:
    schema = _make_schema(PullQuoteBlock(type="pull_quote", text="AI is the new oil."))
    warnings = find_uncited_concrete_claims(schema)
    assert len(warnings) == 1
    assert warnings[0].slot == "pull_quote"


def test_quote_without_source_ids_emits_warning() -> None:
    schema = _make_schema(QuoteBlock(type="quote", text="We hit our guide.", speaker="CFO"))
    warnings = find_uncited_concrete_claims(schema)
    assert len(warnings) == 1
    assert warnings[0].slot == "quote"


def test_multiple_uncited_claims_each_get_their_own_warning() -> None:
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[
                Metric(label="Revenue", value="$95.4B"),
                Metric(label="EPS", value="$2.31"),
                Metric(label="Margin", value="42%", source_ids=["c1"]),
            ],
        ),
        KeyFindingBlock(type="key_finding", content="Margins inflected upward."),
    )
    warnings = find_uncited_concrete_claims(schema)
    kinds = sorted(w.slot for w in warnings)
    assert kinds == ["key_finding", "metric", "metric"]


def test_warning_carries_path_pointing_at_section_id_and_index() -> None:
    """The warning path must locate the offending slot precisely so
    devs can grep / link to it. Format: 'sections[<sid>].blocks[<i>]...'"""
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[Metric(label="Revenue", value="$95.4B")],
        )
    )
    warnings = find_uncited_concrete_claims(schema)
    assert warnings[0].path.startswith("sections[overview].blocks[0]")
    assert "metrics[0]" in warnings[0].path
