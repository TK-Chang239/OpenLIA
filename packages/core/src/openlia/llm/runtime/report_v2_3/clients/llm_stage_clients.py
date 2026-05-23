"""Provider-agnostic LLM-backed clients for PLAN, COMPUTE, SYNTHESIZE,
WRITE and VERIFY.

All five follow the same pattern as ``LLMClarifierClient``: depend only
on a ``json_call(system, user) -> dict`` callable and validate the
return against the relevant Pydantic schema. The wiring layer binds
``SyncJsonLlmClient.call`` for production, tests pass a plain function
returning a canned dict.

Why one module: each prompt is short, the contracts are already in
``schemas.py``, and grouping them keeps the prompt copy + schema
dispatch easy to audit. The fakes still live next to their protocols
in the per-stage client files — production wires the LLM versions
here.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter, ValidationError

from ..schemas import (
    CompsInputs,
    DCFInputs,
    Outline,
    ReportThesis,
    SensitivityInputs,
    ValuationInputs,
    ValuationMethod,
    VerifyResult,
    WrittenSection,
)
from .compute import ComputeClient, ComputeRequest
from .planner import PlannerClient, PlannerRequest
from .synthesizer import SynthesizerClient, SynthesizerRequest
from .verifier import VerifierClient, VerifierRequest
from .writer import WriterClient, WriterRequest

log = logging.getLogger(__name__)

JsonCall = Callable[..., dict[str, Any]]


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


_OUTLINE_ADAPTER: TypeAdapter[Outline] = TypeAdapter(Outline)
_THESIS_ADAPTER: TypeAdapter[ReportThesis] = TypeAdapter(ReportThesis)
_WRITTEN_SECTION_ADAPTER: TypeAdapter[WrittenSection] = TypeAdapter(WrittenSection)
_VERIFY_RESULT_ADAPTER: TypeAdapter[VerifyResult] = TypeAdapter(VerifyResult)
_DCF_INPUTS_ADAPTER: TypeAdapter[DCFInputs] = TypeAdapter(DCFInputs)
_COMPS_INPUTS_ADAPTER: TypeAdapter[CompsInputs] = TypeAdapter(CompsInputs)
_SENSITIVITY_INPUTS_ADAPTER: TypeAdapter[SensitivityInputs] = TypeAdapter(SensitivityInputs)


def _validate(adapter: TypeAdapter, raw: dict[str, Any], stage: str) -> Any:
    try:
        return adapter.validate_python(raw)
    except ValidationError as exc:
        fragment = json.dumps(raw, default=str)[:400]
        raise RuntimeError(
            f"{stage} LLM returned malformed JSON: "
            f"{exc.errors(include_url=False)}; head={fragment!r}"
        ) from exc


# ---------------------------------------------------------------------------
# PLAN
# ---------------------------------------------------------------------------


PLAN_SYSTEM_PROMPT = """You are the PLAN stage of an equity-research report
pipeline. Convert the user's prompt + CLARIFY assumptions into a
section-by-section Outline that tells RESEARCH exactly what evidence to
gather.

Output is a single JSON object matching this Outline shape:

{
  "tickers": ["NVDA"],
  "report_type": "initiation",
  "sections": [
    {
      "id": "business",
      "title": "Business overview",
      "section_type": "qualitative",
      "data_needs": [
        {
          "description": "products, end markets, revenue mix",
          "expected_fact_ids": ["rev_mix_segments", "geo_mix"]
        }
      ]
    }
  ],
  "valuation_plan": {"methods": ["dcf", "comps"]}
}

Rules:

- Pick the smallest set of sections that covers what a PM needs to
  decide on the request. 4-8 is the usual band.
- Every section needs at least one data_need that names what to fetch.
- `expected_fact_ids` are stable handles RESEARCH will try to satisfy
  with that exact id. Match the snake_case naming the rest of the
  pipeline uses.
- `valuation_plan.methods` is the list COMPUTE will execute. Use
  ["dcf"] for initiation, [] for morning_brief / earnings_review,
  ["dcf", "comps"] when peers are visible.
- Output JSON only. No prose, no markdown fences.
""".strip()


def _planner_payload(request: PlannerRequest) -> dict[str, Any]:
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "report_type": request.report_type.value,
        "tickers": list(request.tickers),
        "clarify_result": (
            request.clarify_result.model_dump() if request.clarify_result is not None else None
        ),
    }


class LLMPlannerClient(PlannerClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def plan(self, request: PlannerRequest) -> Outline:
        raw = self._call(system=PLAN_SYSTEM_PROMPT, user=_planner_payload(request))
        return _validate(_OUTLINE_ADAPTER, raw, stage="PLAN")


# ---------------------------------------------------------------------------
# COMPUTE — propose ValuationInputs for a specific method
# ---------------------------------------------------------------------------


COMPUTE_SYSTEM_PROMPT = """You are the COMPUTE stage of an equity-research
report pipeline. The runner will call deterministic ``dcf()`` /
``comps()`` / ``sensitivity()`` math; your job is to propose the
INPUTS that math uses, grounded in the research bundle.

You receive ONE method per call (``dcf``, ``comps``, or
``sensitivity``). Return a single JSON object matching the relevant
input shape:

DCF (``method = "dcf"``):
{
  "revenue_base_fact_id": "rev_ttm",
  "revenue_growth_path": [0.18, 0.14, 0.10, 0.07, 0.05],
  "margin_path":        [0.35, 0.36, 0.37, 0.37, 0.37],
  "wacc": 0.10,
  "terminal_growth": 0.025,
  "tax_rate": 0.21,
  "grounding_fact_ids": ["net_debt", "shares_outstanding"]
}

Comps (``method = "comps"``):
{
  "subject_ticker": "NVDA",
  "peers": [
    {"ticker": "AVGO", "metric_fact_ids": {"ev_ebitda": "peer_avgo_ev_ebitda"}}
  ],
  "multiples": ["ev_ebitda"],
  "subject_metric_fact_ids": {"ev_ebitda": "subject_ebitda_ttm"}
}

Sensitivity (``method = "sensitivity"``):
{
  "base": { ... full DCFInputs above ... },
  "row_driver": "wacc",
  "col_driver": "terminal_growth",
  "row_values": [0.08, 0.09, 0.10, 0.11, 0.12],
  "col_values": [0.02, 0.025, 0.03]
}

Rules:

- All fact ids MUST exist in the supplied bundle. Don't invent ids.
- For DCF, ``revenue_growth_path`` and ``margin_path`` MUST be the
  same length (one entry per projected year).
- For Sensitivity, ``row_driver`` and ``col_driver`` MUST be different.
- Output JSON only.
""".strip()


def _compute_payload(request: ComputeRequest) -> dict[str, Any]:
    return {
        "method": request.method.value,
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "bundle": request.bundle.model_dump(mode="json"),
        "outline": request.outline.model_dump(mode="json"),
        "clarify_result": (
            request.clarify_result.model_dump() if request.clarify_result is not None else None
        ),
    }


_COMPUTE_ADAPTER_BY_METHOD: dict[ValuationMethod, TypeAdapter[Any]] = {
    ValuationMethod.DCF: _DCF_INPUTS_ADAPTER,
    ValuationMethod.COMPS: _COMPS_INPUTS_ADAPTER,
    ValuationMethod.SENSITIVITY: _SENSITIVITY_INPUTS_ADAPTER,
}


class LLMComputeClient(ComputeClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def propose_inputs(self, request: ComputeRequest) -> ValuationInputs:
        raw = self._call(system=COMPUTE_SYSTEM_PROMPT, user=_compute_payload(request))
        adapter = _COMPUTE_ADAPTER_BY_METHOD.get(request.method)
        if adapter is None:
            raise RuntimeError(f"COMPUTE: unknown method {request.method!r}.")
        return _validate(adapter, raw, stage=f"COMPUTE/{request.method.value}")


# ---------------------------------------------------------------------------
# SYNTHESIZE
# ---------------------------------------------------------------------------


SYNTHESIZE_SYSTEM_PROMPT = """You are the SYNTHESIZE stage of an
equity-research report pipeline. Read the research bundle + outline and
produce ONE thesis object that every section writer is conditioned on —
this is what makes parallel section writing cohere.

Output is a single JSON ReportThesis matching:

{
  "language": "en",
  "central_argument": "One sentence the whole report hangs on.",
  "key_takeaways": ["short bullet", "another short bullet"],
  "valuation_stance": "A 1-2 sentence stance: long/short/hold and why.",
  "valuation_plan": {"methods": ["dcf"]},
  "canonical_figures": [
    {"fact_id": "rev_ttm", "display": "$60.9B"}
  ],
  "mandates": [
    {
      "section_id": "business",
      "covers": "what the company does + how revenue lands",
      "does_not_cover": "competitive dynamics (financials covers that)",
      "chart_ids": ["chart_rev_by_segment"],
      "relevant_fact_ids": ["rev_ttm", "rev_mix_segments"]
    }
  ],
  "charts": [
    {
      "id": "chart_rev_by_segment",
      "section_id": "business",
      "claim": "Data Center now dominates the mix.",
      "chart_type": "column",
      "title": "Revenue by segment",
      "category_labels": ["Data Center", "Gaming", "Other"],
      "series": [
        {"name": "FY2025", "value_fact_ids": ["rev_dc_fy25", "rev_gaming_fy25", "rev_other_fy25"]}
      ]
    }
  ]
}

Rules:

- ``language`` MUST equal the request's language.
- ``valuation_plan.methods`` MUST mirror the outline's plan unless
  research shows a method is impossible (e.g. no peers found).
- Every ``mandates[].section_id`` MUST match an outline section.
- Every ``charts[].section_id`` MUST match a mandate; chart fact ids
  MUST be in the bundle; the section's ``relevant_fact_ids`` MUST
  include every fact the chart uses.
- ``canonical_figures[].fact_id`` MUST exist in the bundle and the
  ``display`` string MUST be the final rendering in the report's
  language (e.g. ``$60.9B``, ``14.2%``).
- Output JSON only.
""".strip()


def _synthesize_payload(request: SynthesizerRequest) -> dict[str, Any]:
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "outline": request.outline.model_dump(mode="json"),
        "bundle": request.bundle.model_dump(mode="json"),
        "clarify_result": (
            request.clarify_result.model_dump() if request.clarify_result is not None else None
        ),
    }


class LLMSynthesizerClient(SynthesizerClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def synthesize(self, request: SynthesizerRequest) -> ReportThesis:
        raw = self._call(system=SYNTHESIZE_SYSTEM_PROMPT, user=_synthesize_payload(request))
        return _validate(_THESIS_ADAPTER, raw, stage="SYNTHESIZE")


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------


WRITE_SYSTEM_PROMPT = """You are the WRITE stage of an equity-research
report pipeline. Produce the body of ONE section. The section's mandate
+ the report-wide thesis are your contract — stay inside both.

Output is a single JSON WrittenSection:

{
  "section_id": "business",
  "title": "Business overview",
  "body": "NVIDIA's Data Center revenue reached ${{CITE:rev_dc_fy25}}, a ..."
}

Citation + figure discipline:

- Every numerical claim MUST be supported by a ``{{CITE:fact_id}}``
  placeholder whose fact_id appears in ``relevant_facts``. ASSEMBLE
  numbers footnotes deterministically — you never write [^1] yourself.
- Use ``{{FIG:chart_id}}`` to reference a chart. The chart_id MUST be
  in ``assigned_charts``. ASSEMBLE numbers figures deterministically —
  do not write "Figure 1".
- DON'T cite or reference anything outside the mandate's slice.
- ``does_not_cover`` is a hard boundary — leave that material to its
  owning section.

Rewrite path:

- When ``prior_attempt`` and ``critique`` are present, treat the
  critique as the rewrite brief. Keep what worked; fix what the
  critique flags. Don't expand scope.

Output JSON only.
""".strip()


def _write_payload(request: WriterRequest) -> dict[str, Any]:
    return {
        "section_mandate": request.section_mandate.model_dump(mode="json"),
        "thesis": request.thesis.model_dump(mode="json"),
        "language": request.language.value,
        "relevant_facts": {
            fid: f.model_dump(mode="json") for fid, f in request.relevant_facts.items()
        },
        "assigned_charts": [c.model_dump(mode="json") for c in request.assigned_charts],
        "prior_attempt": (
            request.prior_attempt.model_dump(mode="json")
            if request.prior_attempt is not None
            else None
        ),
        "critique": (
            [i.model_dump(mode="json") for i in request.critique]
            if request.critique is not None
            else None
        ),
    }


class LLMWriterClient(WriterClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def write(self, request: WriterRequest) -> WrittenSection:
        raw = self._call(system=WRITE_SYSTEM_PROMPT, user=_write_payload(request))
        return _validate(_WRITTEN_SECTION_ADAPTER, raw, stage="WRITE")


# ---------------------------------------------------------------------------
# VERIFY
# ---------------------------------------------------------------------------


VERIFY_SYSTEM_PROMPT = """You are the VERIFY stage of an equity-research
report pipeline. Read the drafted sections + the research bundle + the
thesis and surface coherence problems that a writer cannot catch from
inside their own section.

Output is a single JSON VerifyResult:

{
  "issues": [
    {
      "section_id": "valuation",
      "kind": "value_mismatch",
      "severity": "high",
      "detail": "Body says revenue grew 25% but the cited fact rev_yoy_fy25 is 0.42."
    }
  ]
}

What to look for (LLM-only checks — deterministic checks run before
you):

- value_mismatch: prose number disagrees with the cited fact's value.
- cross_section_contradiction: two sections take incompatible stances
  on the same point.
- redundancy: two sections substantially restate the same material.
- chart_text_mismatch: prose describing a chart diverges from what
  the chart's series shows.
- uncited_number: a numerical claim has no ``{{CITE:}}`` token.

Severity:

- ``high``: the runner WILL route the section back to WRITE for a
  bounded retry. Use sparingly — only for issues that change the
  report's takeaway.
- ``low``: surfaced but not blocking.

Return an empty issues list when nothing material is wrong. Output
JSON only.
""".strip()


def _verify_payload(request: VerifierRequest) -> dict[str, Any]:
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "thesis": request.thesis.model_dump(mode="json"),
        "bundle": request.bundle.model_dump(mode="json"),
        "sections": [s.model_dump(mode="json") for s in request.sections],
    }


class LLMVerifierClient(VerifierClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def verify(self, request: VerifierRequest) -> VerifyResult:
        raw = self._call(system=VERIFY_SYSTEM_PROMPT, user=_verify_payload(request))
        return _validate(_VERIFY_RESULT_ADAPTER, raw, stage="VERIFY")


__all__ = [
    "COMPUTE_SYSTEM_PROMPT",
    "PLAN_SYSTEM_PROMPT",
    "SYNTHESIZE_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
    "WRITE_SYSTEM_PROMPT",
    "LLMComputeClient",
    "LLMPlannerClient",
    "LLMSynthesizerClient",
    "LLMVerifierClient",
    "LLMWriterClient",
]
