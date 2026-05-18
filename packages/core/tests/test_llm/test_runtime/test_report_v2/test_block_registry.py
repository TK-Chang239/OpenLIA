from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.packer.blocks.registry import (
    BlockRegistry,
    default_block_registry,
)


def test_register_and_lookup() -> None:
    reg = BlockRegistry()

    def _assemble(data, manifest_resolver):
        return {"type": "x", "value": data["v"]}

    reg.register("x", assembler=_assemble, schema={"type": "object", "required": ["v"]})
    entry = reg.get("x")
    assert entry.assembler is _assemble


def test_unknown_block_returns_none() -> None:
    reg = BlockRegistry()
    assert reg.get("unknown") is None


@pytest.mark.skip(reason="enabled after Tasks 3.3 + 3.4")
def test_default_registry_has_text_table_chart_combo() -> None:
    from openlia.llm.runtime.report_v2.packer.blocks import (
        chart_combo,  # noqa: F401
        table,  # noqa: F401
        text,  # noqa: F401
    )

    assert default_block_registry.get("text") is not None
    assert default_block_registry.get("table") is not None
    assert default_block_registry.get("chart:combo") is not None
