from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment,
    ParsedSection,
    TextSegment,
    parse_section_file,
)

SECTION_FILE = '''---
section_id: industry_overview
title: Industry Overview
sources_used: [1, 3, 7]
word_count_target: 600
synthesis_hooks:
  thesis_contribution: "Edge platform TAM expanding 22% CAGR."
  bull_case_inputs:
    - "Edge compute market 28% CAGR through 2028 [12]"
  bear_case_inputs:
    - "Hyperscalers compressing CDN margins [3]"
---

## Industry Overview

The edge market reached $24.6B in 2025 [12]. Cloudflare commands a meaningful share [3].

```chart:combo
type: combo
title: Edge TAM
series:
  - {name: "Market size ($B)", values: [10, 15, 24.6]}
sources: [12]
```

Continuing analysis [7].
'''


def test_parse_extracts_frontmatter() -> None:
    parsed = parse_section_file(SECTION_FILE)
    assert isinstance(parsed, ParsedSection)
    assert parsed.frontmatter["section_id"] == "industry_overview"
    assert parsed.frontmatter["title"] == "Industry Overview"
    assert parsed.frontmatter["sources_used"] == [1, 3, 7]
    assert parsed.frontmatter["synthesis_hooks"]["thesis_contribution"].startswith("Edge")


def test_parse_segments_preserve_reading_order() -> None:
    parsed = parse_section_file(SECTION_FILE)
    assert len(parsed.segments) == 3
    assert isinstance(parsed.segments[0], TextSegment)
    assert isinstance(parsed.segments[1], FencedBlockSegment)
    assert isinstance(parsed.segments[2], TextSegment)
    assert parsed.segments[1].block_type == "chart:combo"


def test_parse_extracts_citation_markers_from_text() -> None:
    parsed = parse_section_file(SECTION_FILE)
    text_markers = [
        m for s in parsed.segments if isinstance(s, TextSegment) for m in s.citation_ids
    ]
    assert 12 in text_markers
    assert 3 in text_markers
    assert 7 in text_markers


def test_parse_fenced_block_yaml_decoded() -> None:
    parsed = parse_section_file(SECTION_FILE)
    chart = parsed.segments[1]
    assert isinstance(chart, FencedBlockSegment)
    assert chart.data["title"] == "Edge TAM"
    assert chart.data["series"][0]["values"] == [10, 15, 24.6]
    assert chart.data["sources"] == [12]


def test_parse_missing_frontmatter_raises() -> None:
    bad = "## Just a body\n\nNo frontmatter here."
    with pytest.raises(ValueError, match="frontmatter"):
        parse_section_file(bad)


def test_parse_malformed_fence_yaml_raises_with_block_index() -> None:
    bad = '''---
section_id: x
title: X
sources_used: []
---

## Body

```table
title: ok
columns: this is not valid yaml: [it has, a colon issue, in: structure
```
'''
    with pytest.raises(ValueError, match="block 0"):
        parse_section_file(bad)
