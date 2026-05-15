"""Phase 5c: ``source_ids`` field on value-bearing schema slots.

Each structured slot carrying a concrete claim (a number, a quote, a
key finding) accepts ``source_ids: list[str]`` pointing at one or more
entries in ``ReportSchema.citations``. The validator (Phase 5d) emits
a warning when a concrete-claim slot ships with an empty list.

Default is an empty list so existing reports/tests continue to round
trip without modification. The strict-schema constraint (``_Strict``
forbids extra fields) means renderers and the prompt can rely on the
field always being present and well-typed.
"""

from __future__ import annotations

import pytest
from openlia.reports.schema import (
    KeyFindingBlock,
    Metric,
    PullQuoteBlock,
    QuoteBlock,
)
from pydantic import ValidationError


def test_metric_accepts_source_ids() -> None:
    m = Metric(label="Revenue", value="$95.4B", source_ids=["c1", "c2"])
    assert m.source_ids == ["c1", "c2"]


def test_metric_source_ids_defaults_to_empty_list() -> None:
    m = Metric(label="Revenue", value="$95.4B")
    assert m.source_ids == []


def test_key_finding_block_accepts_source_ids() -> None:
    k = KeyFindingBlock(type="key_finding", content="Margins inflected.", source_ids=["c3"])
    assert k.source_ids == ["c3"]


def test_pull_quote_block_accepts_source_ids() -> None:
    q = PullQuoteBlock(type="pull_quote", text="AI is the new oil.", source_ids=["c4"])
    assert q.source_ids == ["c4"]


def test_quote_block_accepts_source_ids() -> None:
    q = QuoteBlock(type="quote", text="Margins expanded.", speaker="CFO", source_ids=["c5"])
    assert q.source_ids == ["c5"]


@pytest.mark.parametrize(
    "model_call",
    [
        lambda sids: Metric(label="x", value="y", source_ids=sids),
        lambda sids: KeyFindingBlock(type="key_finding", content="x", source_ids=sids),
        lambda sids: PullQuoteBlock(type="pull_quote", text="x", source_ids=sids),
    ],
)
def test_source_ids_rejects_non_string_entries(model_call) -> None:
    """Defensive: source_ids must be strings (citation IDs are strings
    on the Citation model). Non-string entries should raise validation
    error rather than silently flowing through."""
    with pytest.raises(ValidationError):
        model_call([1, 2])  # ints, not strings
