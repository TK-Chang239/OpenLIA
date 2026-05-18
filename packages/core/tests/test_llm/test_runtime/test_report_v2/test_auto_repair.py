from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.auto_repair import (
    RepairOutcome,
    repair_section,
)


SECTION_WITH_BAD_TAG = '''---
section_id: x
title: X
sources_used: [1]
---

## Body

Some prose [1].

```combo_chart
title: T
series: [{name: a, values: [1,2,3]}]
```
'''


def test_repair_renames_known_tag_typos() -> None:
    outcome = repair_section(SECTION_WITH_BAD_TAG, known_tags=["chart:combo", "text", "table"])
    assert isinstance(outcome, RepairOutcome)
    assert "```chart:combo" in outcome.markdown
    assert "combo_chart" not in outcome.markdown
    assert outcome.fixes_applied == ["rename_block_tag: combo_chart -> chart:combo"]


def test_repair_leaves_unknown_tags_alone_and_records_warning() -> None:
    src = SECTION_WITH_BAD_TAG.replace("combo_chart", "definitely_not_a_block")
    outcome = repair_section(src, known_tags=["chart:combo", "text", "table"])
    assert "definitely_not_a_block" in outcome.markdown
    assert outcome.warnings != []
