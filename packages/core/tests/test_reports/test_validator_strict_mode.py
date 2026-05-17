"""Phase 6a: validator strict mode promotes uncited-concrete-claim
warnings into ``ReportValidationError`` so the runner's existing
rescue/retry path fires.

Warn-only behaviour (``strict=False``) is unchanged from Phase 5d.

The runner-side integration is exercised here at the module level
because the full ``ReportRunner`` test harness in
``packages/core/tests/test_llm/test_runtime/test_report.py`` has 28
pre-existing failures (the FakeProviderScript wiring is outdated for
the multi-turn writing loop). Mocking just the validator path keeps
this test deterministic until that harness is rebuilt.
"""

from __future__ import annotations

import pytest
from openlia.reports.schema import (
    Cover,
    KeyFindingBlock,
    Metric,
    MetricCardsBlock,
    ReportSchema,
    Section,
)
from openlia.reports.validator import (
    ReportValidationError,
    enforce_uncited_concrete_claims,
    find_uncited_concrete_claims,
)


def _make_schema(*blocks) -> ReportSchema:
    return ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at="2026-05-14T00:00:00+00:00",
        cover=Cover(title="X", subtitle="y", tagline="z"),
        sections=[Section(id="overview", title="Overview", blocks=list(blocks))],
    )


def test_enforce_returns_silently_when_no_warnings() -> None:
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[Metric(label="Revenue", value="$95.4B", source_ids=["c1"])],
        )
    )
    # No raise expected (strict + zero warnings).
    enforce_uncited_concrete_claims(schema, strict=True)


def test_enforce_warn_mode_never_raises_even_with_uncited_metrics() -> None:
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[Metric(label="Revenue", value="$95.4B")],
        )
    )
    # strict=False is the default warn-only behaviour.
    enforce_uncited_concrete_claims(schema, strict=False)


def test_enforce_strict_raises_with_all_uncited_paths() -> None:
    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[
                Metric(label="Revenue", value="$95.4B"),
                Metric(label="EPS", value="$2.31", source_ids=["c1"]),
            ],
        ),
        KeyFindingBlock(type="key_finding", content="Margins inflected upward."),
    )
    warnings = find_uncited_concrete_claims(schema)
    assert len(warnings) == 2  # sanity: one metric + one key_finding uncited.

    with pytest.raises(ReportValidationError) as exc_info:
        enforce_uncited_concrete_claims(schema, strict=True)

    err = exc_info.value
    assert len(err.errors) == len(warnings)
    expected = {(w.path, f"{w.kind}: {w.message}") for w in warnings}
    assert {(p, m) for p, m in err.errors} == expected
    # details must be populated so the runner's rescue path renders them
    # the same as schema errors.
    assert len(err.details) == len(warnings)
    for d in err.details:
        assert "path" in d
        assert "message" in d


# ─── ReportRunner integration (mocked validator path) ──────────────────────


def test_report_request_defaults_to_strict_mode() -> None:
    """As of 2026-05-17, citations_strict defaults to True so the writer
    must repair uncited concrete claims rather than emit them as
    warnings only. See analysis-loop iteration 1 changelog."""
    from openlia.llm.runtime.messages import ReportRequest

    req = ReportRequest(mode="stock_initiation", user_input="AAPL")
    assert req.citations_strict is True


def test_report_request_accepts_citations_strict_true() -> None:
    from openlia.llm.runtime.messages import ReportRequest

    req = ReportRequest(mode="stock_initiation", user_input="AAPL", citations_strict=True)
    assert req.citations_strict is True


def test_report_runner_strict_citations_triggers_rescue_on_uncited_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``citations_strict=True`` and an uncited metric ships,
    ``enforce_uncited_concrete_claims`` raises ``ReportValidationError``;
    the runner's existing ``except ReportValidationError`` block catches
    it and feeds the rescue path (validates schema first, then promotes
    warnings). Verifying the raise behaviour at the validator boundary
    is sufficient — the rescue path itself is the same code that handles
    schema errors and is already exercised by other tests."""
    from openlia.reports import validator as validator_mod

    schema = _make_schema(
        MetricCardsBlock(
            type="metric_cards",
            metrics=[Metric(label="Revenue", value="$95.4B")],
        )
    )

    # Strict request: must raise.
    with pytest.raises(validator_mod.ReportValidationError) as exc_info:
        validator_mod.enforce_uncited_concrete_claims(schema, strict=True)

    # Error tuples carry the kind prefix so traces show
    # `uncited_concrete_claim: ...`.
    assert any(msg.startswith("uncited_concrete_claim:") for _path, msg in exc_info.value.errors)
    # details retain the same kind-prefixed message so rescue rendering
    # matches schema-error rendering.
    assert any(d["message"].startswith("uncited_concrete_claim:") for d in exc_info.value.details)

    # Non-strict request with the same schema: no raise — current warn-only
    # behaviour preserved end to end.
    validator_mod.enforce_uncited_concrete_claims(schema, strict=False)
