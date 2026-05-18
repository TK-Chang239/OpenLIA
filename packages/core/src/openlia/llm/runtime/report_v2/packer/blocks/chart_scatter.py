from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import ScatterBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> ScatterBlock:
    sources = list(data.get("sources", []))
    payload = {k: v for k, v in data.items() if k != "sources"}
    return ScatterBlock(
        type="scatter_plot",
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:scatter", assembler=_assemble)
