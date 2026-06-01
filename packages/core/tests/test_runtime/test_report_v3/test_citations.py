"""Connector-tool source_ids must be citation-safe.

Regression for the same uppercase-source_id bug fixed in Earnings Update:
dispatcher tool names carry uppercase (e.g. ``alphavantage__TOOL_CALL``), but
every citation regex in the engine assumes ``[a-z0-9_]+``. An uppercase
source_id is invisible to the write_section validator, the display-index
assigner, and the rewriter alike, so the model's markers render as raw
``[^alphavantage__TOOL_CALL_1]`` literals with no bibliography link.
"""

from openlia.llm.runtime.report_v3.ledger import CitationLedger
from openlia.llm.runtime.report_v3.rendering.citation_rewriter import (
    CITATION_MARKER_RE,
    rewrite_section_markdown,
)


def test_connector_tool_source_id_is_citation_safe():
    ledger = CitationLedger()
    entry = ledger.append(tool_name="alphavantage__TOOL_CALL")
    assert CITATION_MARKER_RE.fullmatch(f"[^{entry.source_id}]") is not None


def test_connector_citation_resolves_to_display_index():
    ledger = CitationLedger()
    sid = ledger.append(tool_name="alphavantage__TOOL_CALL").source_id
    out = rewrite_section_markdown(
        section_id="thesis",
        title="Thesis",
        markdown=f"Margins expanded.[^{sid}]",
        display_index_by_source_id={sid: 4},
    )
    assert "[^4]" in out.markdown
    assert sid not in out.markdown
