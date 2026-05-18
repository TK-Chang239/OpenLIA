from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.blocks import table, text  # noqa: F401 trigger registration
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.reports.schema import TableBlock, TextBlock


def _resolver(citation_ids):
    return [f"c{i}" for i in citation_ids]


def test_text_assembler_produces_textblock_with_resolved_citations() -> None:
    entry = default_block_registry.get("text")
    assert entry is not None
    block = entry.assembler(
        data={"content": "Edge platform reached $24.6B [12]."},
        citation_ids=[12],
        manifest_resolver=_resolver,
    )
    assert isinstance(block, TextBlock)
    assert block.content == "Edge platform reached $24.6B [12]."
    # TextBlock has no source_ids field in schema — assembler accepts citation_ids
    # but cannot attach them to the block (extra="forbid")


def test_table_assembler_builds_tableblock() -> None:
    entry = default_block_registry.get("table")
    assert entry is not None
    data = {
        "title": "Revenue 5y",
        "headers": [{"key": "year", "label": "Year"}, {"key": "rev", "label": "Revenue ($B)"}],
        "rows": [
            {"year": "2024", "rev": "1.67"},
            {"year": "2023", "rev": "1.30"},
        ],
        "sources": [1],
    }
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, TableBlock)
    assert block.title == "Revenue 5y"
    assert len(block.rows) == 2
    assert block.source_ids == ["c1"]
