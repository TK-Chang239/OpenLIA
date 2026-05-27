"""Provider-agnostic LLM-backed ResearcherClient with a tool-use loop.

This module stays free of OpenAI / Anthropic SDK imports. It depends
only on a tool-use callable with the shape::

    tool_call(system: str, messages: list[Message], tools: list[ToolSchema])
        -> ToolTurnResponse(text=..., tool_calls=...)

The wiring layer chooses the provider (today: OpenAI via
``SyncToolLlmClient``) and binds its ``.send`` method here. Tests pass
a deterministic ``FakeToolLLMClient`` that scripts a turn-by-turn loop.

Researcher contract:

- Loop up to ``max_turns`` turns. Each turn the LLM either calls one
  or more tools OR emits a final text body with a JSON object listing
  the facts it gathered.
- Every tool call result carries a v2.3 ``Provenance`` (from the
  tool's ``ToolResult``). The researcher keeps a ledger keyed by the
  tool call's ``id`` and looks up the provenance when the LLM emits
  a fact that references that id via ``evidence_id``.
- Computed facts (derived from other bundle facts) are emitted with
  ``computed_from`` + ``method`` instead of ``evidence_id``; the
  researcher builds a ``ComputedSource`` for them. (Most computed
  facts come from COMPUTE — this is for cases where RESEARCH simply
  unit-converts a number.)
- Bad / missing evidence_ids raise ``RuntimeError`` with a fragment
  of the offending fact so failures are debuggable.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.llm.types import Citation, Message, ToolCall, ToolSchema

from ..research.tools import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
)
from ..schemas import (
    BundleFact,
    BundleSeries,
    BundleSeriesPoint,
    ComputedSource,
    Provenance,
    ResearchBundle,
    WebSource,
)
from .researcher import ResearcherClient, ResearchRequest

log = logging.getLogger(__name__)


MAX_RESEARCH_TURNS = 12


# ---------------------------------------------------------------------------
# Tool-use LLM Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolTurnResponse:
    """One LLM turn. Either tool_calls is non-empty OR text is.

    ``citations`` carries provider-native source references (today: the
    URL annotations OpenAI's web_search tool attaches inline). The
    researcher converts these into ``WebSource`` provenance entries so
    facts the LLM cites with ``evidence_id: "web_N"`` resolve to a real
    footnote in the rendered report.
    """

    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    citations: tuple[Citation, ...] = ()


class ToolLLMClient(Protocol):
    """Send one turn of a tool-use conversation to the provider."""

    def send(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> ToolTurnResponse: ...


# ---------------------------------------------------------------------------
# Fake — used in tests; scripted turn-by-turn
# ---------------------------------------------------------------------------


class FakeToolLLMClient:
    """Deterministic ToolLLMClient that replays a list of canned turns.

    Each entry in ``turns`` is a ``ToolTurnResponse``. Tests can also
    pass a callable (``responder``) that inspects the message history.
    """

    def __init__(
        self,
        *,
        turns: list[ToolTurnResponse] | None = None,
        responder: Callable[[list[Message]], ToolTurnResponse] | None = None,
    ) -> None:
        if (turns is None) == (responder is None):
            raise ValueError("Provide exactly one of `turns` or `responder`.")
        self._turns = list(turns) if turns is not None else None
        self._responder = responder
        self._next = 0
        self.calls: list[list[Message]] = []
        self.systems: list[str] = []

    def send(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> ToolTurnResponse:
        self.calls.append(list(messages))
        self.systems.append(system)
        if self._responder is not None:
            return self._responder(list(messages))
        assert self._turns is not None
        if self._next >= len(self._turns):
            raise RuntimeError(
                f"FakeToolLLMClient: ran out of scripted turns "
                f"(consumed {self._next}, have {len(self._turns)})."
            )
        out = self._turns[self._next]
        self._next += 1
        return out


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are the RESEARCH stage of an equity-research report pipeline.
Read the outline, fetch facts, emit one JSON object on your last turn.

For every fact, decide what KIND of claim it is:

- Matter of record — exactly one correct value, lives in a filing or
  a market feed. Use the EODHD data tools (`get_fundamentals`,
  `get_historical_prices`, `get_company_news`). Each tool call result
  arrives with an `evidence_id` (e.g. `tc_abc123`) — cite that.
- Matter of interpretation — synthesis, opinion, framing, causal
  claim, forward-looking expectation. Use `web_search`. Each new URL
  the search returns is registered as `web_1`, `web_2`, … in a system
  note. Cite by that `web_N` id.

Cite every fact. Either:
- `evidence_id`: a tool-call id (`tc_…`) or a `web_N` id from a real
  search this run, or
- `computed_from`: list of other fact ids in this same batch, plus
  `method`: a one-line description of how you derived the value.

If you cannot find evidence for a listed fact id after looking, omit
it — don't fabricate a source.

Output one JSON object on your final turn — no prose, no markdown
fences — matching this shape:

{
  "facts": [
    {
      "id": "rev_ttm",
      "label": "Revenue (TTM)",
      "value": 60900000000,
      "unit": "USD",
      "ticker": "<TICKER>",
      "evidence_id": "tc_abc123"
    },
    {
      "id": "rev_growth_5y",
      "label": "Revenue CAGR (5y)",
      "value": 0.42,
      "unit": "percent",
      "ticker": "<TICKER>",
      "computed_from": ["rev_fy2024", "rev_fy2019"],
      "method": "CAGR(rev_fy2019 -> rev_fy2024, 5y)"
    }
  ]
}
""".strip()


# ---------------------------------------------------------------------------
# Researcher
# ---------------------------------------------------------------------------


class LLMResearcherClient(ResearcherClient):
    """Run a bounded tool-use loop and return a populated ResearchBundle."""

    def __init__(
        self,
        llm: ToolLLMClient,
        tools: list[ResearchTool],
        *,
        max_turns: int = MAX_RESEARCH_TURNS,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        self._llm = llm
        self._tools = {t.name: t for t in tools}
        if len(self._tools) != len(tools):
            raise ValueError("Duplicate tool name in tools list.")
        self._tool_schemas = [_descriptor_to_schema(t.descriptor) for t in tools]
        self._max_turns = max_turns

    # -----------------------------------------------------------------
    # ResearcherClient surface
    # -----------------------------------------------------------------

    def research(self, request: ResearchRequest) -> ResearchBundle:
        evidence: dict[str, Provenance] = {}
        web_url_to_id: dict[str, str] = {}
        messages: list[Message] = [Message(role="user", content=_initial_user_text(request))]

        for turn in range(self._max_turns):
            response = self._llm.send(
                system=_system_text(web_url_to_id),
                messages=messages,
                tools=self._tool_schemas,
            )
            prior_urls = len(web_url_to_id)
            self._harvest_web_citations(response.citations, evidence, web_url_to_id)
            new_urls = len(web_url_to_id) - prior_urls
            log.info(
                "v2.3 RESEARCH turn=%d tool_calls=%d citations=%d new_web_urls=%d "
                "web_urls_total=%d",
                turn + 1,
                len(response.tool_calls),
                len(response.citations),
                new_urls,
                len(web_url_to_id),
            )
            if response.tool_calls:
                messages.append(
                    Message(
                        role="assistant",
                        content=response.text or "",
                        tool_calls=tuple(response.tool_calls),
                    )
                )
                for call in response.tool_calls:
                    result_msg, provenance = self._execute_tool_call(call)
                    status = "ok" if provenance is not None else "error"
                    log.info(
                        "v2.3 RESEARCH tool=%s status=%s call_id=%s",
                        call.name,
                        status,
                        call.id,
                    )
                    messages.append(result_msg)
                    if provenance is not None:
                        evidence[call.id] = provenance
                continue

            text = (response.text or "").strip()
            if not text:
                raise RuntimeError(
                    f"RESEARCH LLM emitted neither tool_calls nor text on turn {turn + 1}."
                )
            log.info(
                "v2.3 RESEARCH finished: turns=%d web_urls=%d evidence=%d publishers=%s",
                turn + 1,
                len(web_url_to_id),
                len(evidence),
                _publisher_histogram(web_url_to_id),
            )
            return self._finalize(text, evidence, request)

        raise RuntimeError(
            f"RESEARCH LLM did not emit a final bundle within "
            f"{self._max_turns} turns. Increase max_turns or shrink the outline."
        )

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _harvest_web_citations(
        self,
        citations: tuple[Citation, ...],
        evidence: dict[str, Provenance],
        url_to_id: dict[str, str],
    ) -> None:
        """Convert provider-native URL citations into evidence_id-addressable
        WebSource provenance entries.

        OpenAI's native web_search inlines url_citation annotations and
        emits ``web_search_call`` items whose ``action`` blocks expose
        the URLs the model retrieved. We assign each unique URL a stable
        id of the form ``web_1``, ``web_2`` …, in first-seen order across
        the entire run, and we ALSO key the same Provenance entry by the
        URL itself (and by the URL with toggled trailing slash). This is
        what lets the model cite a web result by ``web_N`` OR by the
        verbatim URL — both forms resolve to the same WebSource. URL
        aliasing is safe because the ``evidence`` dict is populated
        exclusively from URLs the adapter extracted from a real
        ``web_search_call.action`` payload — there is no path for a
        fabricated URL to land here without an actual search returning it.
        """
        for cite in citations:
            url = cite.url
            if not isinstance(url, str) or not url.strip() or cite.kind != "web":
                continue
            if url in url_to_id:
                continue
            web_id = f"web_{len(url_to_id) + 1}"
            url_to_id[url] = web_id
            source = WebSource(
                url=url,
                title=cite.title,
                publisher=cite.source,
                snippet=cite.snippet or (cite.title or url),
                retrieved_at=datetime.now(UTC),
            )
            evidence[web_id] = source
            # URL aliases: model may cite by the literal URL it
            # retrieved. Toggle the trailing slash so LLMs that
            # normalize either way still resolve.
            evidence[url] = source
            alt = url.rstrip("/") if url.endswith("/") else url + "/"
            evidence[alt] = source

    def _execute_tool_call(self, call: ToolCall) -> tuple[Message, Provenance | None]:
        tool = self._tools.get(call.name)
        if tool is None:
            content = json.dumps(
                {"error": f"Unknown tool: {call.name!r}", "available": sorted(self._tools)}
            )
            return Message(role="tool", content=content, tool_call_id=call.id), None
        try:
            result: ToolResult = tool.execute(call.arguments or {})
        except ToolExecutionError as exc:
            content = json.dumps({"error": str(exc)})
            return Message(role="tool", content=content, tool_call_id=call.id), None
        except Exception as exc:
            log.exception("research tool %r raised unexpectedly", call.name)
            content = json.dumps({"error": f"Tool failed: {exc}"})
            return Message(role="tool", content=content, tool_call_id=call.id), None

        body = {
            "evidence_id": call.id,
            "summary": result.summary,
            "payload": result.payload,
        }
        return (
            Message(role="tool", content=json.dumps(body, default=str), tool_call_id=call.id),
            result.provenance,
        )

    def _finalize(
        self,
        text: str,
        evidence: dict[str, Provenance],
        request: ResearchRequest,
    ) -> ResearchBundle:
        parsed = _parse_final_json(text)
        if not isinstance(parsed, dict):
            raise RuntimeError(
                f"RESEARCH LLM final body was not a JSON object: head={text[:200]!r}"
            )
        # Thematic runs: when the planner emitted no data_needs, the
        # researcher legitimately has nothing to fetch. An empty `facts`
        # list is then a valid result, not a failure. A malformed shape
        # (non-list, missing key) is always a protocol violation.
        planner_asked_for_facts = any(section.data_needs for section in request.outline.sections)
        raw_facts = parsed.get("facts")
        if not isinstance(raw_facts, list):
            raise RuntimeError(f"RESEARCH LLM final body had no `facts` array: head={text[:200]!r}")
        if not raw_facts and planner_asked_for_facts:
            raise RuntimeError(
                f"RESEARCH LLM returned an empty `facts` array but the "
                f"planner requested facts: head={text[:200]!r}"
            )

        bundle = ResearchBundle.model_construct(tickers=list(request.tickers), facts={})
        skipped = 0
        rejections: list[tuple[str, str]] = []
        for entry in raw_facts:
            if not isinstance(entry, dict):
                msg = "non-object fact entry"
                log.warning("RESEARCH: skipping %s: %r", msg, entry)
                rejections.append(("<non-object>", f"{msg}: {entry!r}"[:200]))
                skipped += 1
                continue
            try:
                fact = _build_fact(entry, evidence)
            except RuntimeError as exc:
                log.warning(
                    "RESEARCH: skipping malformed fact %r: %s",
                    entry.get("id"),
                    exc,
                )
                rejections.append((str(entry.get("id")), str(exc)))
                skipped += 1
                continue
            if fact.id in bundle.facts:
                log.warning("RESEARCH: skipping duplicate fact id %r.", fact.id)
                rejections.append((fact.id, "duplicate fact id"))
                skipped += 1
                continue
            bundle.facts[fact.id] = fact

        # Prune ComputedSource facts whose `derived_from` references are
        # not in the bundle. Iterate to a fixed point — pruning A can
        # break B if B derived from A. The ResearchBundle model_validator
        # raises on any dangling reference, so we have to repair before
        # re-validating.
        while True:
            dangling = [
                fid
                for fid, fact in bundle.facts.items()
                if isinstance(fact.source, ComputedSource)
                and any(d not in bundle.facts for d in fact.source.derived_from)
            ]
            if not dangling:
                break
            for fid in dangling:
                missing = [
                    d for d in bundle.facts[fid].source.derived_from if d not in bundle.facts
                ]
                log.warning(
                    "RESEARCH: skipping computed fact %r — derives from missing facts %s.",
                    fid,
                    sorted(missing),
                )
                rejections.append((fid, f"dangling computed_from: missing {sorted(missing)}"))
                del bundle.facts[fid]
                skipped += 1

        if not bundle.facts and planner_asked_for_facts:
            raise RuntimeError(
                _no_usable_facts_message(skipped, len(raw_facts), rejections, evidence)
            )

        _enforce_web_coverage_gate(bundle, request)

        # Re-validate the cleaned bundle through Pydantic so downstream
        # stages (COMPUTE re-hydrates from JSON) see the same shape we do.
        return ResearchBundle.model_validate(bundle.model_dump())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_usable_facts_message(
    skipped: int,
    total: int,
    rejections: list[tuple[str, str]],
    evidence: dict[str, Provenance],
) -> str:
    """Compose a diagnostic error when every fact in a non-empty bundle
    was rejected. The bare "skipped N of N" message gives no traction
    for debugging — we surface a category histogram and a few raw
    samples so the next failing run tells you whether the model is
    citing internal step labels, fabricating URLs, leaning on
    `computed_from` with broken refs, or something else."""
    categories: dict[str, int] = {}
    for _fid, reason in rejections:
        key = _classify_reason(reason)
        categories[key] = categories.get(key, 0) + 1
    cat_line = ", ".join(f"{k}={v}" for k, v in sorted(categories.items(), key=lambda kv: -kv[1]))
    sample_lines: list[str] = []
    for fid, reason in rejections[:8]:
        sample_lines.append(f"  - {fid!r}: {reason[:220]}")
    samples = "\n".join(sample_lines)
    web_n = sum(1 for k in evidence if isinstance(k, str) and k.startswith("web_"))
    tc_n = sum(1 for k in evidence if isinstance(k, str) and k.startswith(("tc_", "call_")))
    return (
        f"RESEARCH produced no usable facts (skipped {skipped} of {total}). "
        f"Evidence ledger held web_N={web_n}, tool_call_ids={tc_n}, "
        f"total_keys={len(evidence)} when finalize ran. "
        f"Reason breakdown: {cat_line or '<none>'}.\n"
        f"First rejections:\n{samples or '  <none>'}"
    )


_REASON_PATTERNS: tuple[tuple[str, str], ...] = (
    ("does not match any", "evidence_id_not_in_ledger"),
    ("must specify either", "missing_evidence_and_computed_from"),
    ("evidence_id must be a string", "evidence_id_wrong_type"),
    ("computed_from must be a list", "computed_from_wrong_shape"),
    ("computed_from requires a non-empty", "computed_from_missing_method"),
    ("unsupported value type", "unsupported_value_type"),
    ("missing required string field", "missing_required_field"),
    ("dangling computed_from", "dangling_derivation"),
    ("duplicate fact id", "duplicate_id"),
    ("non-object fact entry", "non_object_entry"),
    ("time-series", "bad_time_series"),
)


def _classify_reason(reason: str) -> str:
    for needle, label in _REASON_PATTERNS:
        if needle in reason:
            return label
    return "other"


def _descriptor_to_schema(descriptor: ToolDescriptor) -> ToolSchema:
    return ToolSchema(
        name=descriptor.name,
        description=descriptor.description,
        parameters=dict(descriptor.parameters),
    )


def _strict_web_ids(request: ResearchRequest) -> set[str]:
    """Ids PLAN listed in some need's ``web_fact_ids`` and not in that
    same need's ``data_fact_ids``. Both the initial-prompt search-budget
    anchor and the finalize-time coverage gate must agree on this set,
    or the model would be told to chase a number the gate doesn't
    enforce."""
    strict: set[str] = set()
    for section in request.outline.sections:
        for need in section.data_needs:
            data_set = set(need.data_fact_ids)
            for fid in need.web_fact_ids:
                if fid not in data_set:
                    strict.add(fid)
    return strict


def _enforce_web_coverage_gate(bundle: ResearchBundle, request: ResearchRequest) -> None:
    """Log web-lane coverage as a soft signal. Does not reject the
    bundle — the relaxed RESEARCH contract lets the bundle through and
    lets downstream stages flag gaps via their own checks."""
    strict_web_ids = _strict_web_ids(request)
    if not strict_web_ids:
        return
    web_covered = {fid for fid, fact in bundle.facts.items() if isinstance(fact.source, WebSource)}
    missing = strict_web_ids - web_covered
    log.info(
        "v2.3 RESEARCH web coverage: strict=%d covered=%d missing=%d",
        len(strict_web_ids),
        len(strict_web_ids & web_covered),
        len(missing),
    )


def _publisher_histogram(url_to_id: dict[str, str]) -> dict[str, int]:
    """Count harvested URLs per registrable host so the run summary log
    surfaces source breadth. Same publisher dominating the bundle is a
    visible signal that web_search queries are not diverse."""
    from urllib.parse import urlparse

    hist: dict[str, int] = {}
    for url in url_to_id:
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            host = ""
        if host.startswith("www."):
            host = host[4:]
        if not host:
            host = "<no-host>"
        hist[host] = hist.get(host, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: (-kv[1], kv[0])))


def _system_text(url_to_id: dict[str, str]) -> str:
    """Compose the per-turn system text, folding in the live web_N mapping.

    The model needs to see the cumulative ``web_N → URL`` table to know
    which ``web_N`` ids are claimable. We inject it into the system text
    (not the message history) so it stays pinned at the top of every
    turn after first harvest and can't scroll out under later tool
    roundtrips. The mapping is the ONLY way the model learns valid
    ``web_N`` ids — raw URLs are not accepted as evidence_ids.
    """
    if not url_to_id:
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n\n{_format_web_search_note(url_to_id)}"


def _format_web_search_note(url_to_id: dict[str, str]) -> str:
    """Render the running ``web_N`` index for the system text.

    Includes a per-publisher histogram line so the model can apply
    step 5 of the narrative-search procedure (steer the next query by
    your results). A model that sees ``By publisher: rocketlab.com=8``
    has a concrete signal — not just a feeling — that its evidence
    pool is single-source and the next search should change angle.
    """
    lines = ["Web search results so far (newest last):"]
    for url, web_id in url_to_id.items():
        lines.append(f"- {web_id}: {url}")
    hist = _publisher_histogram(url_to_id)
    if hist:
        by_pub = ", ".join(f"{host}={n}" for host, n in hist.items())
        lines.append(f"By publisher: {by_pub}")
    lines.append(
        "Cite a web fact with either a `web_N` id above or the exact "
        "URL — both resolve through the same map. URLs not in this "
        "list will not resolve. OpenAI internal step labels "
        "(`turn0search0`, `turn1view2`, etc.) are not accepted."
    )
    return "\n".join(lines)


def _initial_user_text(request: ResearchRequest) -> str:
    sections: list[dict[str, Any]] = []
    for section in request.outline.sections:
        sections.append(
            {
                "id": section.id,
                "title": section.title,
                "data_needs": [
                    {
                        "description": dn.description,
                        "data_fact_ids": list(dn.data_fact_ids),
                        "web_fact_ids": list(dn.web_fact_ids),
                    }
                    for dn in section.data_needs
                ],
            }
        )
    payload = {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "report_type": request.report_type.value,
        "tickers": list(request.tickers),
        "sections": sections,
    }
    return json.dumps(payload, default=str)


_FENCE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def _parse_final_json(text: str) -> Any:
    """Extract the final JSON object from the model's last turn.

    Tolerant of Claude-style prose-then-fenced-JSON output: tries direct
    parse, then any ```json ... ``` block, then a first-`{` to last-`}`
    substring, in that order."""
    stripped = _strip_fence(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Last fenced block wins — if the model wrote a draft block then a
    # revised one, the revision should be the one we honor.
    fence_matches = _FENCE_BLOCK_RE.findall(text)
    for body in reversed(fence_matches):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            continue

    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(stripped[first : last + 1])
        except json.JSONDecodeError:
            pass
    raise RuntimeError(
        f"RESEARCH LLM final body was not valid JSON: head={text[:200]!r} tail={text[-200:]!r}"
    )


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _build_fact(
    entry: dict[str, Any],
    evidence: dict[str, Provenance],
) -> BundleFact:
    fid = _require_str(entry, "id")
    label = _require_str(entry, "label")
    value = _coerce_value(entry.get("value"), fid)
    unit = entry.get("unit")
    ticker = entry.get("ticker")

    evidence_id = entry.get("evidence_id")
    computed_from = entry.get("computed_from")
    method = entry.get("method")

    source: Provenance
    if evidence_id:
        if not isinstance(evidence_id, str):
            raise RuntimeError(f"Fact {fid!r}: evidence_id must be a string, got {evidence_id!r}.")
        if evidence_id not in evidence:
            raise RuntimeError(
                f"Fact {fid!r}: evidence_id {evidence_id!r} does not match any "
                f"tool call, web_N id, or URL the runtime harvested this run."
            )
        source = evidence[evidence_id]
    elif computed_from:
        ok_list = isinstance(computed_from, list) and all(isinstance(x, str) for x in computed_from)
        if not ok_list:
            raise RuntimeError(f"Fact {fid!r}: computed_from must be a list of strings.")
        if not isinstance(method, str) or not method.strip():
            raise RuntimeError(f"Fact {fid!r}: computed_from requires a non-empty `method`.")
        source = ComputedSource(method=method.strip(), derived_from=list(computed_from))
    else:
        raise RuntimeError(
            f"Fact {fid!r}: must specify either `evidence_id` or `computed_from`+`method`."
        )

    return BundleFact(
        id=fid,
        label=label,
        value=value,
        unit=unit if isinstance(unit, str) else None,
        ticker=ticker if isinstance(ticker, str) else None,
        source=source,
    )


def _coerce_value(raw: Any, fact_id: str) -> float | str | BundleSeries:
    if isinstance(raw, bool):
        # bool is an int subclass; reject before the (int, float) branch
        # eats it as 0/1.
        return str(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        # Try numeric strings ("1500000", "1.5e9", "$60.9B", "14.2%") so
        # an LLM that quotes its numbers still produces a usable fact.
        coerced = _try_parse_number(raw)
        return coerced if coerced is not None else raw
    if isinstance(raw, dict) and "points" in raw:
        points_raw = raw.get("points") or []
        if not isinstance(points_raw, list) or not points_raw:
            raise RuntimeError(f"Fact {fact_id!r}: time-series `points` must be a non-empty list.")
        points = []
        for p in points_raw:
            if not isinstance(p, dict):
                log.warning("Fact %r: dropping non-object point %r from time-series.", fact_id, p)
                continue
            period = p.get("period")
            if not isinstance(period, str):
                log.warning("Fact %r: dropping point with non-string period %r.", fact_id, period)
                continue
            value = p.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                if isinstance(value, str):
                    parsed = _try_parse_number(value)
                    if parsed is not None:
                        points.append(BundleSeriesPoint(period=period, value=parsed))
                        continue
                log.warning(
                    "Fact %r: dropping point %r with non-numeric value %r.",
                    fact_id,
                    period,
                    value,
                )
                continue
            points.append(BundleSeriesPoint(period=period, value=float(value)))
        if not points:
            raise RuntimeError(
                f"Fact {fact_id!r}: time-series `points` had no usable numeric points "
                f"(check the LLM is emitting one metric per fact, not a packed line-item dump)."
            )
        unit = raw.get("unit")
        return BundleSeries(points=points, unit=unit if isinstance(unit, str) else None)
    raise RuntimeError(f"Fact {fact_id!r}: unsupported value type {type(raw).__name__}.")


_NUMBER_SUFFIXES: tuple[tuple[str, float], ...] = (
    ("t", 1_000_000_000_000.0),
    ("b", 1_000_000_000.0),
    ("m", 1_000_000.0),
    ("k", 1_000.0),
)


def _try_parse_number(s: str) -> float | None:
    """Best-effort coercion of human-formatted numbers ($1.5B, 14.2%, etc.).
    Returns None when the string clearly isn't numeric so callers can fall
    back to keeping it as a string label."""
    cleaned = s.strip().replace(",", "").replace("$", "").replace("_", "")
    if not cleaned:
        return None
    is_percent = cleaned.endswith("%")
    if is_percent:
        cleaned = cleaned[:-1].strip()
    multiplier = 1.0
    if cleaned and cleaned[-1].lower() in {"t", "b", "m", "k"}:
        suffix = cleaned[-1].lower()
        for token, mult in _NUMBER_SUFFIXES:
            if token == suffix:
                multiplier = mult
                cleaned = cleaned[:-1].strip()
                break
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def _require_str(entry: dict[str, Any], key: str) -> str:
    val = entry.get(key)
    if not isinstance(val, str) or not val.strip():
        raise RuntimeError(f"Fact entry missing required string field {key!r}: {entry!r}")
    return val.strip()


__all__ = [
    "MAX_RESEARCH_TURNS",
    "SYSTEM_PROMPT",
    "FakeToolLLMClient",
    "LLMResearcherClient",
    "ToolLLMClient",
    "ToolTurnResponse",
]
