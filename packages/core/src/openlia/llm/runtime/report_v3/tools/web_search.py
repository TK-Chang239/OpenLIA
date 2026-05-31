"""Native web_search tool — descriptor + ledger ingest.

v3 does NOT register web_search as a function tool the runner
dispatches. Instead the model invokes the provider's first-class web
search via ``LLMRequest.native_tools=("web_search",)``; the adapter
calls the upstream API and returns the results as
``LLMResponse.citations`` (Citation objects with kind="web").

This module exposes two things:

1. ``WEB_SEARCH_TOOL_NAME`` — the canonical name the runner threads
   into the LLMRequest and uses in system-prompt language.
2. ``ingest_web_citations(citations, ledger)`` — after every model
   turn, the runner calls this to append any new web citations to the
   v3 ledger and return a mapping of ``citation.id -> source_id`` so
   the runner can rewrite the assistant message to reference v3
   source_ids instead of raw provider citation ids.

The descriptor itself is exposed so the system prompt and tool count
stay coherent, but it is NOT included in the function-tool catalog
the runner dispatches — the adapter handles it natively.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from ...report_v2_3.research import ToolDescriptor
from ...report_v2_3.schemas import WebSource
from ..ledger import CitationLedger

WEB_SEARCH_TOOL_NAME = "web_search"


def build_web_search_descriptor() -> ToolDescriptor:
    """Descriptor used for documentation in the system prompt only.

    The runner does not register this as a dispatched tool — the
    provider's native web_search handles it. We expose the descriptor
    so the prompt builder can list it alongside the dispatched tools.
    """
    return ToolDescriptor(
        name=WEB_SEARCH_TOOL_NAME,
        description=(
            "Run a web search via the provider's first-class search tool. "
            "Results carry stable source_ids (web_1, web_2, ...) you can "
            "cite directly in section markdown as `[^web_N]`. Use this for "
            "narrative context EODHD doesn't cover: news, product launches, "
            "regulatory commentary, management quotes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    )


def ingest_web_citations(citations: Iterable, ledger: CitationLedger) -> dict[str, str]:
    """Append any new web citations to the ledger.

    Takes ``LLMResponse.citations`` (an iterable of v2.3 ``Citation``
    objects). For each citation with kind="web" that isn't already in
    the ledger (matched by URL), appends a new entry. Returns a
    mapping of ``citation.id -> source_id`` the runner can use to
    rewrite assistant messages so the model sees v3 source_ids
    in subsequent turns.

    Skips non-web citations (kind="tool" / "memory") — those are
    accounted for by the dispatched tool execution path.
    """
    url_to_source_id: dict[str, str] = {
        entry.provenance.get("url", ""): entry.source_id
        for entry in ledger.all()
        if entry.tool_name == WEB_SEARCH_TOOL_NAME
    }
    rewrites: dict[str, str] = {}
    for cite in citations:
        if getattr(cite, "kind", None) != "web":
            continue
        url = getattr(cite, "url", None) or ""
        if not url:
            continue
        existing_source_id = url_to_source_id.get(url)
        if existing_source_id:
            rewrites[cite.id] = existing_source_id
            continue
        provenance = WebSource(
            url=url,
            title=getattr(cite, "title", None),
            publisher=getattr(cite, "source", None),
            snippet=getattr(cite, "snippet", None) or "",
            retrieved_at=datetime.now(UTC),
        )
        entry = ledger.append(
            tool_name=WEB_SEARCH_TOOL_NAME,
            arguments={"url": url},
            result_summary=(getattr(cite, "title", None) or url)[:200],
            provenance=provenance.model_dump(mode="json"),
        )
        rewrites[cite.id] = entry.source_id
        url_to_source_id[url] = entry.source_id
    return rewrites


def format_web_citation_notice(citations: Iterable, rewrites: dict[str, str]) -> str | None:
    """Build a message body announcing the ``[^web_N]`` ids the model can cite.

    Native web-search results don't flow through the ledger-annotated
    tool-result path the dispatched tools use, so the model never sees
    the ``web_N`` source_id assigned to each result — it falls back to
    the provider's own citation markers (``<cite index=...>`` /
    ``[^6-1]``), which don't resolve to the bibliography. Feeding this
    notice back into the conversation after a turn that did web search
    teaches the model the exact markers to use.

    Returns ``None`` when the turn surfaced no web citations.
    """
    lines: list[str] = []
    seen: set[str] = set()
    for cite in citations:
        if getattr(cite, "kind", None) != "web":
            continue
        source_id = rewrites.get(getattr(cite, "id", ""))
        if source_id is None or source_id in seen:
            continue
        seen.add(source_id)
        url = getattr(cite, "url", None) or ""
        title = (getattr(cite, "title", None) or url or "web source").strip()
        line = f'- [^{source_id}]: "{title}"'
        if url:
            line += f" ({url})"
        lines.append(line)
    if not lines:
        return None
    header = (
        "The web search you just ran returned these sources. They are now "
        "citable. When a claim draws on one, cite it inline with the exact "
        "marker shown below (e.g. [^web_1]) — do not use any other citation "
        "format."
    )
    return header + "\n" + "\n".join(lines)
