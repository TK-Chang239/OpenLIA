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
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from openlia.llm.types import Message, ToolCall, ToolSchema

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
)
from .researcher import ResearcherClient, ResearchRequest

log = logging.getLogger(__name__)


MAX_RESEARCH_TURNS = 12


# ---------------------------------------------------------------------------
# Tool-use LLM Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolTurnResponse:
    """One LLM turn. Either tool_calls is non-empty OR text is."""

    text: str
    tool_calls: tuple[ToolCall, ...] = ()


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

    def send(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> ToolTurnResponse:
        self.calls.append(list(messages))
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


SYSTEM_PROMPT = """You are the RESEARCH stage of an equity-research report
pipeline. Your job: gather the facts the rest of the pipeline will use
to write the report, and emit them as a single JSON object on your
last turn.

How you work:

1. Read the user's outline, especially each section's `data_needs`.
   Each data_need is a piece of evidence WRITE will cite — your job is
   to fetch it.

2. Call tools to collect evidence. You can call multiple tools per
   turn. Re-call tools as needed. Each tool call result is labeled
   with `evidence_id` — that's the handle you use later to cite it.

3. When you have enough evidence to cover the outline, STOP calling
   tools. On your final turn emit exactly one JSON object — no prose,
   no markdown fences — matching this shape:

```
{
  "facts": [
    {
      "id": "rev_ttm",
      "label": "Revenue (TTM)",
      "value": 60900000000,
      "unit": "USD",
      "ticker": "NVDA",
      "evidence_id": "tc_abc123"
    },
    {
      "id": "rev_growth_5y",
      "label": "Revenue CAGR (5y)",
      "value": 0.42,
      "unit": "percent",
      "ticker": "NVDA",
      "computed_from": ["rev_fy2024", "rev_fy2019"],
      "method": "CAGR(rev_fy2019 -> rev_fy2024, 5y)"
    }
  ]
}
```

Rules:

- Every fact MUST have either `evidence_id` (pointing at a tool call
  that returned the number) OR both `computed_from` (list of other
  fact ids in this batch) AND `method` (one-line description).
- Each `value` is a single atomic data point: a number, a date, a
  ticker, or a short label (twelve words or fewer). For multi-period
  data, use a time-series object
  `{"points": [{"period": "2025-Q4", "value": 60.9}, ...], "unit": "USD_billions"}`.
  Save narrative prose for SYNTHESIZE / WRITE — RESEARCH facts stay
  compact so the downstream stages can compose freely.
- Fact ids are stable handles — choose short, snake_case strings.
- Emit a fact only when a tool call returned the data. Skip facts
  with no tool-call backing so WRITE can flag the gap.
- Every fact must trace to a tool call (or to other facts in this
  batch via `computed_from` + `method`).
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
        messages: list[Message] = [Message(role="user", content=_initial_user_text(request))]

        for turn in range(self._max_turns):
            response = self._llm.send(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=self._tool_schemas,
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
                    messages.append(result_msg)
                    if provenance is not None:
                        evidence[call.id] = provenance
                continue

            text = (response.text or "").strip()
            if not text:
                raise RuntimeError(
                    f"RESEARCH LLM emitted neither tool_calls nor text on turn {turn + 1}."
                )
            return self._finalize(text, evidence, request)

        raise RuntimeError(
            f"RESEARCH LLM did not emit a final bundle within "
            f"{self._max_turns} turns. Increase max_turns or shrink the outline."
        )

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

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
        raw_facts = parsed.get("facts")
        if not isinstance(raw_facts, list) or not raw_facts:
            raise RuntimeError(f"RESEARCH LLM final body had no `facts` array: head={text[:200]!r}")

        bundle = ResearchBundle(tickers=list(request.tickers))
        for entry in raw_facts:
            if not isinstance(entry, dict):
                raise RuntimeError(f"Fact entry must be an object, got: {entry!r}")
            fact = _build_fact(entry, evidence)
            bundle.add(fact)
        return bundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _descriptor_to_schema(descriptor: ToolDescriptor) -> ToolSchema:
    return ToolSchema(
        name=descriptor.name,
        description=descriptor.description,
        parameters=dict(descriptor.parameters),
    )


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
                        "expected_fact_ids": list(dn.expected_fact_ids),
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


def _parse_final_json(text: str) -> Any:
    stripped = _strip_fence(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(stripped[first : last + 1])
        except json.JSONDecodeError:
            pass
    raise RuntimeError(f"RESEARCH LLM final body was not valid JSON: head={text[:200]!r}")


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _build_fact(entry: dict[str, Any], evidence: dict[str, Provenance]) -> BundleFact:
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
                f"Fact {fid!r}: evidence_id {evidence_id!r} does not match any tool call."
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
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict) and "points" in raw:
        points_raw = raw.get("points") or []
        if not isinstance(points_raw, list) or not points_raw:
            raise RuntimeError(f"Fact {fact_id!r}: time-series `points` must be a non-empty list.")
        points = []
        for p in points_raw:
            if not isinstance(p, dict):
                raise RuntimeError(f"Fact {fact_id!r}: point must be an object.")
            period = p.get("period")
            value = p.get("value")
            if not isinstance(period, str):
                raise RuntimeError(f"Fact {fact_id!r}: point.period must be a string.")
            if not isinstance(value, (int, float)):
                raise RuntimeError(f"Fact {fact_id!r}: point.value must be numeric.")
            points.append(BundleSeriesPoint(period=period, value=float(value)))
        unit = raw.get("unit")
        return BundleSeries(points=points, unit=unit if isinstance(unit, str) else None)
    raise RuntimeError(f"Fact {fact_id!r}: unsupported value type {type(raw).__name__}.")


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
