"""Stage 5 planner: decides which helpers to invoke and at what fidelity.

Per artifact-injection §4. The planner emits a PlannerOutput that Stage 7a
uses (via template_defaults.resolve_section_plan) to build the resolved
ReportSectionPlan before materialization.

The LLM call is synchronous (asyncio.run on the async generate) so the
planner is callable from synchronous orchestrator code.  Callers that are
already async should await planner.aplan() instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

from .enums import Fidelity
from .section_plan import PlannerOverrides, SectionPlanOverride

logger = logging.getLogger(__name__)

_PROMPTS_SHARED = Path(__file__).parent.parent.parent.parent / "prompts" / "shared"


# ---------------------------------------------------------------------------
# Planner output schema
# ---------------------------------------------------------------------------


class HelperInvocation(BaseModel):
    """Describes one helper call for a specific section artifact."""

    helper_name: str
    params: dict[str, Any] = {}
    artifact_id: str  # artifact_id this invocation should bind its output to


class HelperSelection(BaseModel):
    """One entry per template section."""

    section_id: str
    helpers: list[HelperInvocation]


class PlannerOutput(BaseModel):
    """Top-level Stage 5 output.

    helper_selection: which helpers to run per section
    planner_overrides: fidelity / brief overrides on top of template defaults
    open_questions: questions the planner could not resolve from context
    cross_section_themes: short strings that thread across sections
    """

    helper_selection: list[HelperSelection]
    planner_overrides: list[PlannerOverrides]
    open_questions: list[str] = []
    cross_section_themes: list[str] = []


# ---------------------------------------------------------------------------
# Prompt builder (pure Python, no LLM)
# ---------------------------------------------------------------------------


def _load_planner_prompt_template() -> str:
    path = _PROMPTS_SHARED / "planner_v2_2.yaml.j2"
    if not path.exists():
        raise FileNotFoundError(f"Planner prompt not found at {path}")
    return path.read_text()


def _render_planner_prompt(
    ticker: str,
    template_id: str,
    sections: list[dict[str, Any]],
    available_helpers: list[dict[str, Any]],
) -> str:
    """Render the planner system prompt with Jinja2."""
    from jinja2 import Environment, StrictUndefined

    template_src = _load_planner_prompt_template()
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    tmpl = env.from_string(template_src)
    return tmpl.render(
        ticker=ticker,
        template_id=template_id,
        sections=sections,
        available_helpers=available_helpers,
    )


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_planner_response(text: str) -> PlannerOutput:
    """Parse LLM JSON response into PlannerOutput.

    Strips markdown code fences if present.  Raises ValueError on malformed
    JSON; raises ValidationError on schema mismatch.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        # Strip opening fence (```json or ```)
        lines = stripped.splitlines()
        # Find closing fence
        end = next((i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"), None)
        inner = lines[1:end] if end else lines[1:]
        stripped = "\n".join(inner).strip()

    try:
        raw: dict[str, Any] = json.loads(stripped)
    except json.JSONDecodeError as exc:
        tail = stripped[-400:] if len(stripped) > 400 else stripped
        raise ValueError(
            f"planner_v2_2 returned malformed JSON ({exc.msg} at line {exc.lineno} "
            f"col {exc.colno}). Response length={len(stripped)} chars. "
            f"Last 400 chars: {tail!r}. "
            "Most common cause: the planner LLM hit its max_tokens cap and the "
            "JSON was truncated mid-string. Raise Planner(max_tokens=...) or pick "
            "a model whose per-call output cap is at least 8k tokens."
        ) from exc

    # Normalise: planner_overrides may be a list of raw dicts already matching
    # PlannerOverrides, or may need the overrides.overrides nesting.
    planner_overrides_raw: list[Any] = raw.get("planner_overrides", [])
    parsed_overrides: list[PlannerOverrides] = []
    for po in planner_overrides_raw:
        if isinstance(po, dict):
            # Ensure overrides field is a list of SectionPlanOverride
            raw_ovs = po.get("overrides", [])
            overrides = [SectionPlanOverride.model_validate(o) for o in raw_ovs]
            parsed_overrides.append(
                PlannerOverrides(
                    template_id=po.get("template_id", ""),
                    overrides=overrides,
                    rationale=po.get("rationale", ""),
                )
            )

    # Normalise helper_selection
    helper_selection_raw: list[Any] = raw.get("helper_selection", [])
    parsed_selections: list[HelperSelection] = []
    for hs in helper_selection_raw:
        if isinstance(hs, dict):
            helpers = [HelperInvocation.model_validate(h) for h in hs.get("helpers", [])]
            parsed_selections.append(
                HelperSelection(
                    section_id=hs.get("section_id", ""),
                    helpers=helpers,
                )
            )

    return PlannerOutput(
        helper_selection=parsed_selections,
        planner_overrides=parsed_overrides,
        open_questions=raw.get("open_questions", []),
        cross_section_themes=raw.get("cross_section_themes", []),
    )


# ---------------------------------------------------------------------------
# Planner class
# ---------------------------------------------------------------------------


class Planner:
    """Stage 5 planner: calls the LLM to produce PlannerOutput.

    Usage (synchronous):
        planner = Planner(llm=provider, ticker="MSFT", template=spec)
        output = planner.plan()

    Usage (async):
        output = await planner.aplan()
    """

    def __init__(
        self,
        llm: LLMProvider,
        ticker: str,
        template_sections: list[dict[str, Any]],
        available_helpers: list[dict[str, Any]] | None = None,
        template_id: str = "stock_initiation_v2",
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> None:
        """
        Args:
            llm: LLMProvider to call.
            ticker: Stock ticker, e.g. "MSFT".
            template_sections: List of section dicts with keys section_id, title,
                default_artifacts (list of {artifact_id, fidelity}).
            available_helpers: Optional list of helper dicts {name, category, one_liner}.
                Defaults to empty list — callers should inject from helper registry.
            template_id: Template identifier, e.g. "stock_initiation_v2".
            max_tokens: Token budget for the planner LLM call.
            temperature: Sampling temperature (low for determinism).
        """
        self._llm = llm
        self._ticker = ticker
        self._template_id = template_id
        self._template_sections = template_sections
        self._available_helpers = available_helpers or []
        self._max_tokens = max_tokens
        self._temperature = temperature

    def _build_request(self) -> LLMRequest:
        system_prompt = _render_planner_prompt(
            ticker=self._ticker,
            template_id=self._template_id,
            sections=self._template_sections,
            available_helpers=self._available_helpers,
        )
        return LLMRequest(
            messages=[Message(role="user", content="Produce the planner output now.")],
            system=system_prompt,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

    async def aplan(self) -> PlannerOutput:
        """Async plan: calls LLM and returns PlannerOutput."""
        request = self._build_request()
        response = await self._llm.generate(request)
        logger.debug(
            "Planner LLM response: %d input tokens, %d output tokens, finish=%s",
            response.input_tokens,
            response.output_tokens,
            response.finish_reason,
        )
        # Detect provider-reported truncation up front. Different adapters use
        # different finish_reason strings ("length", "max_tokens",
        # "MAX_TOKENS"); normalise and treat any of them as truncation.
        if response.finish_reason and response.finish_reason.lower() in (
            "length",
            "max_tokens",
        ):
            raise ValueError(
                f"planner_v2_2 LLM output was truncated by the provider "
                f"(finish_reason={response.finish_reason!r}, "
                f"output_tokens={response.output_tokens}, "
                f"requested max_tokens={self._max_tokens}). The planner emits "
                "structured JSON; truncation produces unparseable output. Raise "
                "Planner(max_tokens=...) or pick a model with a larger per-call "
                "output cap."
            )
        return _parse_planner_response(response.text)

    def plan(self) -> PlannerOutput:
        """Synchronous plan: runs aplan() in a new event loop.

        Must not be called from within a running event loop (e.g. inside a
        FastAPI route handler) — doing so raises RuntimeError because
        asyncio.run() cannot be called when a loop is already running.
        Production callers in async contexts must use ``await planner.aplan()``
        directly. The RunnerV2 pipeline calls ``aplan()`` via the
        ThreadPoolExecutor guard in ``_stage_planner_v2_2()`` to avoid this.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            raise RuntimeError(
                "Planner.plan() was called from within a running event loop. "
                "Use 'await planner.aplan()' instead, or drive the runner via "
                "RunnerV2 which uses the ThreadPoolExecutor guard."
            )
        return asyncio.run(self.aplan())


# ---------------------------------------------------------------------------
# Convenience: build template_sections from a TemplateSpecV2
# ---------------------------------------------------------------------------


def sections_from_spec(spec: Any) -> list[dict[str, Any]]:
    """Convert a TemplateSpecV2 into the list format Planner expects.

    Falls back gracefully if the spec has no sections attribute.
    """
    sections: list[dict[str, Any]] = []
    for s in getattr(spec, "sections", []):
        artifacts: list[dict[str, Any]] = []
        for art in getattr(spec, "required_artifacts", []):
            target = getattr(art, "target_section_id", None)
            if target == s.id:
                artifacts.append(
                    {
                        "artifact_id": art.id,
                        "fidelity": Fidelity.FULL.value,
                    }
                )
        sections.append(
            {
                "section_id": s.id,
                "title": s.name,
                "default_artifacts": artifacts,
            }
        )
    return sections
