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


def _call_with_repair(
    *,
    json_call: JsonCall,
    system: str,
    user: Any,
    adapter: TypeAdapter,
    stage: str,
    sanitiser: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    post_validator: Callable[[Any], list[str]] | None = None,
    max_retries: int = 1,
) -> Any:
    """Call the LLM, validate, and on failure re-prompt once with the
    errors so the model can self-repair.

    This absorbs most of the "Stage X raised: malformed JSON" failures
    we hit in production: the model violates a constraint (invalid
    enum, dangling reference, missing field), the schema flags exactly
    what's wrong, and we hand the model its own output + the error list
    and ask it to fix only what's broken. One retry is enough for ~70%
    of these — beyond that the model is genuinely confused and we
    should fail loud rather than burn tokens on the same problem.

    Three failure modes are caught uniformly:
    - **Pydantic ValidationError** from `adapter.validate_python` —
      missing fields, invalid enums, wrong types.
    - **Post-validation complaints** from `post_validator(parsed)` —
      cross-reference checks the schema cannot express (e.g. "this
      chart's fact_id doesn't exist in the bundle"). Returning a
      non-empty list of error strings triggers a repair.
    - **Sanitiser repair** — `sanitiser` runs before validation and
      fixes deterministic patterns silently (drop invalid enum values).
      Anything it cannot fix falls through to repair.
    """

    def _try(raw: dict[str, Any]) -> tuple[Any, list[Any] | None]:
        """Sanitise + validate + post-validate. Returns (parsed, errors).
        On success, errors is None. On failure, errors is the list of
        complaints to feed back to the LLM."""
        cleaned = sanitiser(raw) if sanitiser is not None else raw
        try:
            parsed = adapter.validate_python(cleaned)
        except ValidationError as exc:
            return None, exc.errors(include_url=False)
        if post_validator is not None:
            complaints = post_validator(parsed)
            if complaints:
                return None, complaints
        return parsed, None

    raw = json_call(system=system, user=user)
    parsed, last_errors = _try(raw)
    if parsed is not None:
        return parsed
    last_raw = raw

    for attempt in range(max_retries):
        log.warning(
            "%s: validation failed (attempt %d/%d), asking LLM to repair. First error: %s",
            stage,
            attempt + 1,
            max_retries + 1,
            last_errors[0] if last_errors else "<none>",
        )
        repair_user = {
            "original_request": user,
            "your_previous_output": last_raw,
            "validation_errors": last_errors,
            "instruction": (
                "Your previous JSON output failed validation. Re-emit the "
                "FULL corrected JSON object addressing the errors above. "
                "Keep every part of your previous output that was valid — "
                "only change what the errors flag. Output JSON only, no "
                "prose."
            ),
        }
        raw = json_call(system=system, user=repair_user)
        parsed, last_errors = _try(raw)
        if parsed is not None:
            return parsed
        last_raw = raw

    fragment = json.dumps(last_raw, default=str)[:400]
    raise RuntimeError(
        f"{stage} LLM returned malformed JSON after {max_retries + 1} attempts: "
        f"{last_errors}; head={fragment!r}"
    )


# ---------------------------------------------------------------------------
# PLAN
# ---------------------------------------------------------------------------


PLAN_SYSTEM_PROMPT = """
You are the PLAN stage of the v2.3 equity-research engine. The user
template supplies the section structure; your job is to fill each
section with the data_needs RESEARCH should fetch and to select the
valuation methods COMPUTE should run.

Inputs you receive:
- raw_prompt: the user's request.
- template.sections: the ordered list of sections the report must
  contain. Each section carries an `id`, `title`, `intent`, and
  optional `methodology_hints`.
- clarify_result: the assumptions resolved at CLARIFY.

Output an Outline JSON object:
{
  "tickers": ["NVDA"],
  "report_type": "initiation",
  "sections": [
    {
      "id": "<copy from template.sections[i].id>",
      "title": "<copy from template.sections[i].title>",
      "data_needs": [
        {
          "description": "<one-line note on what RESEARCH should fetch>",
          "expected_fact_ids": ["rev_ttm", "rev_growth_yoy"]
        }
      ]
    },
    ...
  ],
  "valuation_plan": {
    "methods": ["dcf", "comps"]
  }
}

Rules:
- Produce one section per template.sections entry, in the same order,
  with the same `id` and `title`. The engine's coercer will fix drift,
  so be conservative — copy the structure verbatim.
- For each section, populate `data_needs` with one or more entries.
  Each `data_needs[*].expected_fact_ids` is a list of stable identifier
  strings RESEARCH will fetch and bind to the BundleFact map. Use
  snake_case ids like `rev_ttm`, `gross_margin_fy25`, `peer_ev_ebitda`.
- `valuation_plan.methods` lists the valuation methods COMPUTE should
  run. Choose from `dcf`, `comps`, `sensitivity` based on what the
  template's sections actually need (e.g. include `dcf` only when a
  section's intent calls for an intrinsic valuation).
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
        "template": {
            "template_id": request.template.template_id,
            "name": request.template.name,
            "shape_description": request.template.shape_description,
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "intent": s.intent,
                    "methodology_hints": list(s.methodology_hints),
                }
                for s in request.template.sections
            ],
        },
    }


class LLMPlannerClient(PlannerClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def plan(self, request: PlannerRequest) -> Outline:
        return _call_with_repair(
            json_call=self._call,
            system=PLAN_SYSTEM_PROMPT,
            user=_planner_payload(request),
            adapter=_OUTLINE_ADAPTER,
            stage="PLAN",
        )


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
        adapter = _COMPUTE_ADAPTER_BY_METHOD.get(request.method)
        if adapter is None:
            raise RuntimeError(f"COMPUTE: unknown method {request.method!r}.")
        return _call_with_repair(
            json_call=self._call,
            system=COMPUTE_SYSTEM_PROMPT,
            user=_compute_payload(request),
            adapter=adapter,
            stage=f"COMPUTE/{request.method.value}",
        )


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
  "central_argument": "ONE SHORT SENTENCE — max 20 words. Hard cap.",
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

- ``central_argument`` is the cover hero — keep it to ONE sentence,
  ≤ 20 words, no clauses chained with "but"/"however" that bury the
  punchline. The longer "why" belongs in ``valuation_stance``.
- ``language`` MUST equal the request's language.
- ``valuation_plan.methods`` MUST mirror the outline's plan unless
  research shows a method is impossible (e.g. no peers found).
- Every ``mandates[].section_id`` MUST match an outline section.
- Each outline section carries a ``template_intent`` field capturing what
  the user's template asked the section to accomplish; ground each
  mandate's ``covers`` text in that intent so writers know exactly what
  the user wanted from this section.
- Every ``charts[].section_id`` MUST match a mandate; chart fact ids
  MUST be in the bundle; the section's ``relevant_fact_ids`` MUST
  include every fact the chart uses.
- ``charts[].chart_type`` MUST be one of EXACTLY these values:
  ``"column"``, ``"bar"``, ``"line"``, ``"area"``, ``"pie"``,
  ``"scatter"``. Do NOT invent other values (no ``"text"``,
  ``"table"``, ``"heatmap"``, etc. — if the data wouldn't plot as one
  of the six, omit the chart). Each ChartSpec needs at least one
  series with at least one fact_id; if you can't satisfy that, drop
  the chart rather than emit a placeholder.
- ``mandates[].chart_ids`` is a strict subset of ``charts[].id``. NEVER
  name a chart in a mandate that you didn't also define in ``charts``;
  if a section shouldn't have a chart, leave ``chart_ids`` as ``[]``.
- ``canonical_figures[].fact_id`` MUST exist in the bundle and the
  ``display`` string MUST be the final rendering in the report's
  language (e.g. ``$60.9B``, ``14.2%``).
- Output JSON only.

Chart-selection guide — pick the form that fits the data, not the
form that's easiest to fill:

- ``line``: time-series of ONE metric across >= 4 periods. Use this for
  revenue trajectory, price history, margin trend over years. If the
  bundle carries only 2-3 periods, do NOT make a line — write the
  comparison in prose and skip the chart.
- ``area``: same shape as line but when you want to emphasise the
  cumulative magnitude (e.g. stacked revenue mix over time). Avoid
  single-series area; line conveys the same trend cleaner.
- ``column`` (vertical bars): cross-sectional comparison of 3-10
  categories of the SAME metric (revenue by segment, employees by
  region, capex by year-bucket). Each category must be meaningfully
  comparable — apples-to-apples.
- ``bar`` (horizontal): use when category labels are long (full peer
  names, country names). Same data shape as column otherwise.
- ``pie``: composition / share-of-total ONLY, where the parts sum to
  a meaningful whole (revenue mix by segment, geographic split). Cap
  at 5-7 slices. Never use pie for trends, comparisons across time,
  or unrelated quantities.
- ``scatter``: relationship between TWO numeric variables across many
  entities (peer P/E vs. growth, ROIC vs. leverage). Minimum ~5
  points; fewer than that and the relationship isn't visible.

Anti-patterns — do NOT do these (they are the most common bad chart
choices we see):

- Two-bar column / bar charts (e.g. 52-week low vs. high; this-year vs.
  last-year revenue). Two data points is a sentence, not a chart.
  Write it in prose and cite the facts.
- One-point line / area / column (chart with a single data point is
  meaningless — just cite the number).
- Pie chart of unrelated metrics (e.g. "revenue + EBITDA + FCF" in
  one pie — they don't sum to anything).
- Range / endpoint charts (52-week range, target-price range): we
  don't have a range chart type. Either show the full time series as
  a line (if you have it) or omit the chart and quote the endpoints.
- Charts whose ``claim`` is generic ("shows financial performance",
  "displays valuation metrics"). If you cannot write a one-sentence,
  non-obvious insight the chart proves, the chart isn't earning its
  page space — drop it.
- Mixing units inside one series. Every fact in
  ``series.value_fact_ids`` MUST share the same ``unit`` value (look
  at ``bundle.facts[fact_id].unit``). A series cannot plot
  ``USD_millions`` next to ``USD`` next to ``percent`` — the y-axis
  becomes meaningless and one bar dwarfs the rest. Example of the
  bug we're trying to avoid: plotting DCF enterprise value
  (``USD_millions``, ~30,000) next to per-share comps targets
  (``USD``, ~$3,000) on the same column chart — one bar reads as a
  trillion, the rest as flat. If your candidate facts span units,
  EITHER convert/derive new facts in a single unit (e.g. compute
  per-share equivalents for everything) OR omit the chart.

If the bundle doesn't support a section's chart well, leave that
``mandates[].chart_ids`` empty rather than forcing a weak chart.
""".strip()


def _synthesize_payload(request: SynthesizerRequest) -> dict[str, Any]:
    # Enrich each outline section with the matching template section's
    # `intent` so the synthesizer can ground each mandate's `covers`
    # text in the user's stated intent rather than the LLM's reading of
    # the section title alone. The enrichment lives inline next to the
    # section dict so the LLM reads the two together.
    intents_by_id: dict[str, str] = {s.id: s.intent for s in request.template.sections}
    outline_payload = request.outline.model_dump(mode="json")
    for section in outline_payload.get("sections", []):
        section["template_intent"] = intents_by_id.get(section.get("id", ""), "")
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "outline": outline_payload,
        "bundle": request.bundle.model_dump(mode="json"),
        "clarify_result": (
            request.clarify_result.model_dump() if request.clarify_result is not None else None
        ),
    }


# Mirrors ``ChartType`` in schemas.py — duplicated here so the SYNTHESIZE
# pre-validation pass can sanitise charts without importing the enum and
# coupling the prompt to schema internals.
_VALID_CHART_TYPES = frozenset({"column", "bar", "line", "area", "pie", "scatter"})


def _sanitise_synthesize_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce an LLM-emitted thesis dict into a shape the validator will
    accept, dropping LLM noise that doesn't justify failing the run.

    Specifically:
    - Charts with a ``chart_type`` outside the engine's enum are dropped
      (the LLM occasionally invents "text" / "table" / "heatmap").
    - Mandate ``chart_ids`` that no longer point at a real chart (because
      we dropped the chart above, OR because the LLM hallucinated the
      id) are stripped from the mandate. The section then renders
      without that chart instead of failing the whole run.
    - Canonical figure entries whose ``fact_id`` is malformed
      (non-string, empty) are dropped — the per-fact existence check
      against the bundle still runs in the stage validator and catches
      genuine misses.

    The result still goes through full Pydantic validation, so any
    structural problem this pass doesn't recognise still surfaces.
    """
    if not isinstance(raw, dict):
        return raw

    # 1. Drop charts whose chart_type isn't in the enum.
    charts = raw.get("charts")
    surviving_chart_ids: set[str] = set()
    if isinstance(charts, list):
        sanitised_charts: list[Any] = []
        for chart in charts:
            if not isinstance(chart, dict):
                continue
            ct = chart.get("chart_type")
            cid = chart.get("id")
            if isinstance(ct, str) and ct in _VALID_CHART_TYPES:
                sanitised_charts.append(chart)
                if isinstance(cid, str):
                    surviving_chart_ids.add(cid)
            else:
                log.warning(
                    "SYNTHESIZE: dropping chart with unsupported chart_type=%r (id=%r)",
                    ct,
                    cid,
                )
        raw["charts"] = sanitised_charts

    # 2. Strip phantom chart_ids from mandates (chart was dropped above
    #    OR the LLM hallucinated an id that never appeared in charts).
    mandates = raw.get("mandates")
    if isinstance(mandates, list):
        for mandate in mandates:
            if not isinstance(mandate, dict):
                continue
            cids = mandate.get("chart_ids")
            if not isinstance(cids, list):
                continue
            kept = [c for c in cids if isinstance(c, str) and c in surviving_chart_ids]
            phantom = [c for c in cids if c not in kept]
            if phantom:
                log.warning(
                    "SYNTHESIZE: stripping phantom chart_ids %r from mandate %r",
                    phantom,
                    mandate.get("section_id"),
                )
                mandate["chart_ids"] = kept

    # 3. Drop canonical_figures entries with malformed fact_ids; the
    #    bundle-existence check in the stage validator still catches
    #    references to facts that simply don't exist.
    cfs = raw.get("canonical_figures")
    if isinstance(cfs, list):
        raw["canonical_figures"] = [
            cf
            for cf in cfs
            if isinstance(cf, dict) and isinstance(cf.get("fact_id"), str) and cf["fact_id"].strip()
        ]

    return raw


def _thesis_bundle_complaints(thesis: ReportThesis, bundle: Any) -> list[str]:
    """Structured error list for thesis -> bundle cross-references.

    Returns one string per phantom reference the LLM emitted. The
    repair loop feeds these back so the LLM can either fix the
    reference (use a real fact_id) or drop the chart / canonical_figure
    on the retry — instead of us silently stripping and leaving the
    LLM unaware. Empty list means everything resolves.

    `bundle` is typed loosely (Any) to keep the client module free of
    a circular import; we only call `bundle.facts.keys()` on it.
    """
    fact_ids = set(bundle.facts.keys())
    complaints: list[str] = []

    bad_canonical = [cf.fact_id for cf in thesis.canonical_figures if cf.fact_id not in fact_ids]
    if bad_canonical:
        complaints.append(
            f"canonical_figures reference fact_ids that do not exist in the bundle: "
            f"{sorted(set(bad_canonical))}. Use only ids from the bundle facts map, "
            f"or drop the canonical_figure entry."
        )

    for chart in thesis.charts:
        missing = chart.referenced_fact_ids() - fact_ids
        if missing:
            complaints.append(
                f"chart '{chart.id}' series.value_fact_ids reference fact_ids that "
                f"do not exist in the bundle: {sorted(missing)}. Either use real "
                f"fact_ids from the bundle, or omit the chart entirely if no "
                f"suitable facts exist."
            )
            # Skip the unit check when refs are bad — units of missing
            # facts can't be inspected and the missing-refs complaint
            # already tells the LLM to repair this chart.
            continue
        for series in chart.series:
            units = {bundle.facts[fid].unit or "" for fid in series.value_fact_ids}
            if len(units) > 1:
                detail = {fid: bundle.facts[fid].unit for fid in series.value_fact_ids}
                complaints.append(
                    f"chart '{chart.id}' series '{series.name}' mixes unit types "
                    f"across its value_fact_ids: {detail}. A single series must "
                    f"share one unit (the y-axis is meaningless otherwise — one "
                    f"value will dwarf the rest). Either pick facts that share "
                    f"a unit, derive intermediate facts in a common unit, or "
                    f"omit the chart."
                )

    chart_ids = {c.id for c in thesis.charts}
    for mandate in thesis.mandates:
        phantom_charts = set(mandate.chart_ids) - chart_ids
        if phantom_charts:
            complaints.append(
                f"mandate for section '{mandate.section_id}' references chart_ids "
                f"that you did not define in the charts array: {sorted(phantom_charts)}."
            )
        missing_facts = set(mandate.relevant_fact_ids) - fact_ids
        if missing_facts:
            complaints.append(
                f"mandate for section '{mandate.section_id}' references fact_ids "
                f"that do not exist in the bundle: {sorted(missing_facts)}."
            )

    return complaints


class LLMSynthesizerClient(SynthesizerClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def synthesize(self, request: SynthesizerRequest) -> ReportThesis:
        # The post_validator closure captures the bundle so the LLM
        # gets a structured complaint when its chart/canonical/mandate
        # refs miss real fact_ids — this is what was causing reports to
        # ship with zero charts (the LLM invented chart_rev_2022 style
        # ids and the silent-strip in the stage dropped the whole chart).
        return _call_with_repair(
            json_call=self._call,
            system=SYNTHESIZE_SYSTEM_PROMPT,
            user=_synthesize_payload(request),
            adapter=_THESIS_ADAPTER,
            stage="SYNTHESIZE",
            sanitiser=_sanitise_synthesize_raw,
            post_validator=lambda thesis: _thesis_bundle_complaints(thesis, request.bundle),
        )


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
  "body": "NVIDIA's Data Center revenue reached {{CITE:rev_dc_fy25}}, a ..."
}

Length budget — match the requested ``length``:

- ``concise``:     ~150-250 words. One tight paragraph or two short ones.
                   Surface only the load-bearing facts; skip nuance.
- ``normal``:      ~300-500 words. 2-3 paragraphs. Headline + supporting
                   detail + a forward-looking note.
- ``elaborative``: ~600-900 words. 3-5 paragraphs. Add second-order
                   detail, counterpoints, and quantified context.

Length is a target band, not a hard ceiling. Don't pad to reach it; if
the bundle only supports a shorter section, write the shorter section.

Number grammar — every number in the body comes from one of three markers.
The engine resolves all three to {{CITE:<id>}} before VERIFY runs, so the
report's reader sees consistent footnotes; the deterministic check after
you write will reject any digit-bearing token outside these markers.

1. Cite an existing fact when the number already lives in the bundle:
     {{CITE:rev_ttm}}
   Use this whenever the bundle already carries the value you want to claim.

2. Derive a new fact from existing ones when the number is arithmetic
   over bundle facts (growth rates, YoY deltas, ratios):
     {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}}
   Grammar: {{DERIVE:<method>|<input_fact_ids_csv>|<new_fact_id>}}
   Methods available: growth_rate, yoy_delta, ratio.
   The engine runs the math, mints a ComputedSource fact at <new_fact_id>,
   and rewrites your marker to {{CITE:<new_fact_id>}}.

3. State an estimate when the number is analyst judgment with no
   underlying calculation — projections, scenario calls, view-driven
   targets:
     {{ESTIMATE:upside_pct|0.10|percent|projection from margin-expansion thesis}}
   Grammar: {{ESTIMATE:<new_fact_id>|<value>|<unit>|<basis>}}
   The engine mints an EstimateSource fact at <new_fact_id> with your
   basis text as the footnote, and rewrites your marker to
   {{CITE:<new_fact_id>}}. The footnote will render as
   "Estimate: <basis>." so the reader sees this is judgment, not a
   measured figure.

Exemptions (the deterministic check ignores these): 4-digit years
("2025"), fiscal-year tokens ("FY2025"), quarter labels ("Q3"), and
ordinals ("3rd"). Anything else with a digit needs one of the three
markers.

Worked example (showing all three):
  "Revenue {{CITE:rev_ttm}} grew
   {{DERIVE:growth_rate|rev_ttm,rev_prior|rev_growth_yoy}} year over year,
   and we see {{ESTIMATE:upside_pct|0.10|percent|
   margin expansion against current multiple}} of further upside."

Marker rendering notes:

- ``{{CITE:fact_id}}`` is a self-contained insertion: the ASSEMBLE
  stage replaces the token with the fact's FORMATTED VALUE AND a
  superscript footnote, e.g. "{{CITE:revenue_ttm}}" becomes
  "$451.4B [^7]". Write the surrounding prose around the marker as if
  it were already a noun phrase carrying the number — leave currency
  symbols, units, and the numeric value to the engine so you don't end
  up with "$$451.4B [^7]" or stray decorations.
- For ``{{CITE:fact_id}}``, the fact_id should appear in
  ``relevant_facts``. Use real ids from that map.
- ``{{FIG:chart_id}}`` references a chart by id from ``assigned_charts``.
  ASSEMBLE rewrites it as "Figure N" — write the marker where you want
  the chart anchored in the prose and let the engine number it.
- Stay inside the mandate's slice. ``does_not_cover`` is a hard
  boundary — leave that material to its owning section.

Examples (good vs bad):

  GOOD: "Revenue reached {{CITE:revenue_ttm}} in the trailing twelve
         months, up from prior years."
  BAD:  "Revenue reached ${{CITE:revenue_ttm}} in the trailing twelve
         months."                              ^ stray "$" survives

  GOOD: "The stock trades at {{CITE:forward_pe}} forward earnings."
  BAD:  "The stock trades at [^15] forward earnings."  ^ leave [^N] to the engine

Rewrite path:

- When ``prior_attempt`` and ``critique`` are present, treat the
  critique as the rewrite brief. Keep what worked; fix what the
  critique flags. Don't expand scope.

Output JSON only.
""".strip()


def _write_payload(request: WriterRequest) -> dict[str, Any]:
    # Key ordering is deliberate for OpenAI prompt-caching: the prefix
    # of the user message must be byte-identical across the N parallel
    # WRITE calls for the cache to hit. ``language``, ``length``, and
    # ``thesis`` are identical for every section in a run, so we serialize
    # them FIRST. The section-specific bits (mandate, facts, charts,
    # retry context) come last so they form the cache-miss tail. Result:
    # roughly one section's worth of input billed, not six.
    return {
        "language": request.language.value,
        "length": request.length.value,
        "thesis": request.thesis.model_dump(mode="json"),
        "section_mandate": request.section_mandate.model_dump(mode="json"),
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
        return _call_with_repair(
            json_call=self._call,
            system=WRITE_SYSTEM_PROMPT,
            user=_write_payload(request),
            adapter=_WRITTEN_SECTION_ADAPTER,
            stage="WRITE",
        )


# ---------------------------------------------------------------------------
# VERIFY
# ---------------------------------------------------------------------------


VERIFY_SYSTEM_PROMPT = """You are the VERIFY stage of an equity-research
report pipeline. Read the drafted sections + the thesis and surface
coherence problems that a writer cannot catch from inside their own
section.

You receive only the sections and the thesis — the full research bundle
is NOT in your input. A deterministic check has already validated every
``{{CITE:fact_id}}`` against the bundle and confirmed each cited value
resolves; your job is the qualitative read.

Output is a single JSON VerifyResult:

{
  "issues": [
    {
      "section_id": "valuation",
      "kind": "cross_section_contradiction",
      "severity": "high",
      "detail": "Valuation says margins expanding but financials show compression."
    }
  ]
}

What to look for (LLM-only checks — deterministic checks already cover
value_mismatch and uncited_number, so leave both to the runner and
focus on coherence-level concerns):

- cross_section_contradiction: two sections take incompatible stances
  on the same point.
- redundancy: two sections substantially restate the same material.
- chart_text_mismatch: prose describing a chart diverges from what
  the chart's series shows (chart series are listed inline on the
  thesis).
- thesis_drift: a section's takeaway contradicts the central_argument
  or valuation_stance.

Severity:

- ``high``: the runner WILL route the section back to WRITE for a
  bounded retry. Use sparingly — only for issues that change the
  report's takeaway.
- ``low``: surfaced but not blocking.

Return an empty issues list when nothing material is wrong. Output
JSON only.
""".strip()


def _verify_payload(request: VerifierRequest) -> dict[str, Any]:
    # Bundle deliberately omitted — deterministic CITE re-resolution
    # already validates every numeric claim against the bundle. The LLM
    # verifier only needs the prose + the thesis to do its qualitative
    # checks (contradictions, redundancy, chart-text drift), which
    # roughly halves VERIFY input cost.
    return {
        "language": request.language.value,
        "thesis": request.thesis.model_dump(mode="json"),
        "sections": [s.model_dump(mode="json") for s in request.sections],
        "raw_prompt": request.raw_prompt,
    }


_VALID_VERIFY_KINDS = frozenset(
    {
        "uncited_number",
        "dangling_cite",
        "value_mismatch",
        "cross_section_contradiction",
        "redundancy",
        "chart_text_mismatch",
        "broken_fig_ref",
        "thesis_drift",
    }
)


def _sanitise_verify_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop verify issues with unknown `kind` values. The schema enum
    is finite; an LLM that names a kind we don't have ("hallucination",
    "tone_mismatch") should not nuke the entire VERIFY result — we
    keep the issues we recognise and log the strays.
    """
    if not isinstance(raw, dict):
        return raw
    issues = raw.get("issues")
    if not isinstance(issues, list):
        return raw
    kept: list[Any] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        kind = issue.get("kind")
        if isinstance(kind, str) and kind in _VALID_VERIFY_KINDS:
            kept.append(issue)
        else:
            log.warning(
                "VERIFY: dropping issue with unknown kind=%r (section=%r, detail=%r).",
                kind,
                issue.get("section_id"),
                (issue.get("detail") or "")[:120],
            )
    raw["issues"] = kept
    return raw


class LLMVerifierClient(VerifierClient):
    def __init__(self, json_call: JsonCall) -> None:
        self._call = json_call

    def verify(self, request: VerifierRequest) -> VerifyResult:
        return _call_with_repair(
            json_call=self._call,
            system=VERIFY_SYSTEM_PROMPT,
            user=_verify_payload(request),
            adapter=_VERIFY_RESULT_ADAPTER,
            stage="VERIFY",
            sanitiser=_sanitise_verify_raw,
        )


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
