from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401 trigger registration
    bullet_list,
    callout_grid,
    comparison_split,
    group,
    key_finding,
    metric_cards,
    pull_quote,
    quote,
    rating_badge,
    text,
    timeline,
)
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.reports.schema import (
    BulletListBlock,
    CalloutGridBlock,
    ComparisonSplitBlock,
    GroupBlock,
    KeyFindingBlock,
    MetricCardsBlock,
    PullQuoteBlock,
    QuoteBlock,
    RatingBadgeBlock,
    TextBlock,
    TimelineBlock,
)


def _resolver(citation_ids):
    return [f"c{i}" for i in citation_ids]


REMAINING_CASES = [
    (
        "metric_cards",
        MetricCardsBlock,
        {
            "metrics": [
                {"label": "Revenue", "value": "$10B", "delta": "+5%", "delta_direction": "up"},
                {"label": "EPS", "value": "$3.50"},
            ]
        },
    ),
    (
        "key_finding",
        KeyFindingBlock,
        {
            "content": "Cloud growth accelerating to 35% YoY.",
            "sources": [2],
        },
    ),
    (
        "rating_badge",
        RatingBadgeBlock,
        {
            "rating": "Buy",
            "previous_rating": "Hold",
            "change_date": "2024-01-15",
        },
    ),
    (
        "pull_quote",
        PullQuoteBlock,
        {
            "text": "We are just getting started.",
            "attribution": "CEO",
            "sources": [3],
        },
    ),
    (
        "callout_grid",
        CalloutGridBlock,
        {
            "columns": 2,
            "items": [
                {
                    "eyebrow": "Pillar 1",
                    "title": "Cloud",
                    "description": "Fastest growing segment.",
                },
                {"title": "AI", "description": "Copilot driving adoption."},
            ],
        },
    ),
    (
        "timeline",
        TimelineBlock,
        {
            "title": "Key Catalysts",
            "events": [
                {"when": "Q1 2024", "what": "Azure OpenAI GA", "impact": "Revenue inflection"},
                {
                    "when": "Q3 2024",
                    "what": "Copilot+ PCs launch",
                    "impact": "Positive",
                    "impact_tag": {"label": "bull", "tone": "positive"},
                    "highlight": True,
                },
            ],
        },
    ),
    (
        "bullet_list",
        BulletListBlock,
        {
            "items": ["Strong free cash flow", "Market share gains", "AI tailwinds"],
            "tone": "positive",
        },
    ),
    (
        "comparison_split",
        ComparisonSplitBlock,
        {
            "left": {
                "title": "Bulls",
                "tone": "positive",
                "items": ["Cloud momentum", "AI optionality"],
            },
            "right": {
                "title": "Bears",
                "tone": "negative",
                "items": ["Valuation stretched", "FX headwind"],
            },
        },
    ),
    (
        "quote",
        QuoteBlock,
        {
            "text": "==AI is the electricity of our era.==",
            "speaker": "Satya Nadella",
            "role": "CEO",
            "tag": {"label": "bullish", "tone": "positive"},
            "sources": [5],
        },
    ),
]


@pytest.mark.parametrize("tag,cls,data", REMAINING_CASES)
def test_remaining_assembler_returns_expected_class(tag, cls, data) -> None:
    entry = default_block_registry.get(tag)
    assert entry is not None, f"{tag} not registered"
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, cls)


def test_key_finding_resolves_citations() -> None:
    entry = default_block_registry.get("key_finding")
    assert entry is not None
    block = entry.assembler(
        data={"content": "Cloud grew 35%.", "sources": [7]},
        citation_ids=[],
        manifest_resolver=_resolver,
    )
    assert block.source_ids == ["c7"]


def test_group_recursive_assembles_child_blocks() -> None:
    """group assembler must recursively resolve child blocks via registry."""
    entry = default_block_registry.get("group")
    assert entry is not None
    data = {
        "type": "group",
        "columns": 2,
        "blocks": [
            {"type": "text", "content": "Child text block."},
            {"type": "key_finding", "content": "Key insight.", "sources": [1]},
        ],
    }
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, GroupBlock)
    assert block.columns == 2
    assert len(block.blocks) == 2
    assert isinstance(block.blocks[0], TextBlock)
    assert isinstance(block.blocks[1], KeyFindingBlock)
    assert block.blocks[1].source_ids == ["c1"]


def test_key_finding_accepts_text_alias() -> None:
    # Report 82e063b6 shipped 7 omitted key_finding blocks because the LLM
    # reached for ``text`` instead of ``content``. Aliases must survive.
    entry = default_block_registry.get("key_finding")
    assert entry is not None
    block = entry.assembler(
        data={"text": "Margins expanded 220bps."},
        citation_ids=[],
        manifest_resolver=_resolver,
    )
    assert isinstance(block, KeyFindingBlock)
    assert block.content == "Margins expanded 220bps."


def test_pull_quote_accepts_quote_alias() -> None:
    entry = default_block_registry.get("pull_quote")
    assert entry is not None
    block = entry.assembler(
        data={"quote": "We are accelerating.", "author": "CFO"},
        citation_ids=[],
        manifest_resolver=_resolver,
    )
    assert isinstance(block, PullQuoteBlock)
    assert block.text == "We are accelerating."
    assert block.attribution == "CFO"


def test_callout_grid_accepts_body_alias() -> None:
    entry = default_block_registry.get("callout_grid")
    assert entry is not None
    block = entry.assembler(
        data={
            "items": [
                {"heading": "Pillar 1", "body": "Workflow automation."},
                {"title": "Pillar 2", "description": "AI integration."},
            ]
        },
        citation_ids=[],
        manifest_resolver=_resolver,
    )
    assert isinstance(block, CalloutGridBlock)
    assert block.items[0].title == "Pillar 1"
    assert block.items[0].description == "Workflow automation."
    assert block.items[1].title == "Pillar 2"


def test_timeline_accepts_date_and_event_aliases() -> None:
    entry = default_block_registry.get("timeline")
    assert entry is not None
    block = entry.assembler(
        data={
            "events": [
                {"date": "2024-Q3", "event": "Launched Now Assist."},
                {"when": "2024-11", "what": "Acquired Element AI."},
            ]
        },
        citation_ids=[],
        manifest_resolver=_resolver,
    )
    assert isinstance(block, TimelineBlock)
    assert block.events[0].when == "2024-Q3"
    assert block.events[0].what == "Launched Now Assist."


def test_group_raises_on_unknown_child_type() -> None:
    entry = default_block_registry.get("group")
    assert entry is not None
    with pytest.raises(ValueError, match="unknown child block type"):
        entry.assembler(
            data={
                "type": "group",
                "columns": 1,
                "blocks": [{"type": "does_not_exist", "content": "x"}],
            },
            citation_ids=[],
            manifest_resolver=_resolver,
        )
