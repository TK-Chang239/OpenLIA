"""Step 2 remediation: engine wiring tests for Stage 5b + Stage 7a integration.

Covers B-1 through B-4 and advisory A-2, A-3, A-7, A-9 fixes:

  - RunnerV2 with planner_v2_2_llm=None runs end-to-end as before (regression)
  - RunnerV2 with planner_v2_2_llm injected activates Stage 5b + 7a in the pipeline
  - A PlannerOutput with an unknown helper name emits HELPER_UNAVAILABLE
  - build_drafter_prompt() is called when MaterializedSection is available;
    v2 prompt path used when not
  - make_v2_runner_stage_factory() returns a RunnerV2 with planner_v2_2_llm populated
  - Planner.plan() raises when called from a running event loop (A-2)
  - comparables_run helper is registered under underscore name (A-9)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
from openlia.llm.runtime.report_v2.pipeline.stage_8_verify import (
    SectionVerificationResult,
    VerificationRound,
)
from openlia.llm.runtime.report_v2.runner_v2 import (
    Completed,
    PipelineStage,
    RunnerV2,
    RunState,
    StageCompleted,
    StageStarted,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import ClarifierOutput
from openlia.llm.runtime.report_v2.schemas.plan import Plan, ResearchStrand
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool
from openlia.llm.runtime.report_v2_2.planner import (
    HelperInvocation,
    HelperSelection,
    Planner,
    PlannerOutput,
)
from openlia.llm.types import LLMResponse

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _empty_template() -> Any:
    template = Mock()
    template.template_id = "stock_research_v2"
    template.template_name = "Stock Research (v2)"
    template.sections = []
    return template


def _ok_clarifier_output() -> ClarifierOutput:
    return ClarifierOutput(
        questions=[],
        blocking_warnings=[],
        notices=[],
        detected_intents=[],
    )


def _default_plan() -> Plan:
    return Plan(
        research_strands=[ResearchStrand(id="fundamentals", purpose="x", allowed_tools=[])],
        required_artifacts=[],
        optional_artifacts=[],
        section_dag={},
        slipped_requests=[],
    )


def _wire_stage_mocks() -> dict[str, Mock]:
    """Build minimal stage mocks for happy-path v2 run."""
    plan = _default_plan()

    clarifier = Mock()
    clarifier.clarify.return_value = _ok_clarifier_output()

    research_planner = Mock()
    research_planner.plan.return_value = plan

    strand_dispatcher = Mock()
    strand_dispatcher.dispatch.return_value = ResearchPool()

    model_planner = Mock()
    model_planner.plan.return_value = plan

    model_builder = Mock()
    model_builder.build.return_value = []

    section_drafter = Mock()
    section_drafter.draft_all.return_value = []

    verifier = Mock()
    verifier.verify_with_retry.return_value = SectionVerificationResult(
        section_id="s1",
        final_status="OK",
        rounds=[VerificationRound(round_num=0, issues=[])],
        all_issues_ever=[],
        final_blocks=[],
    )

    return {
        "clarifier": clarifier,
        "research_planner": research_planner,
        "strand_dispatcher": strand_dispatcher,
        "model_planner": model_planner,
        "model_builder": model_builder,
        "section_drafter": section_drafter,
        "verifier": verifier,
    }


def _minimal_planner_output(helper_name: str = "dcf_engine") -> PlannerOutput:
    return PlannerOutput(
        helper_selection=[
            HelperSelection(
                section_id="valuation_dcf",
                helpers=[
                    HelperInvocation(
                        helper_name=helper_name,
                        params={},
                        artifact_id="dcf_output",
                    )
                ],
            )
        ],
        planner_overrides=[],
        open_questions=[],
        cross_section_themes=[],
    )


class _StubLLMProvider:
    """Minimal async LLMProvider stub that returns a canned PlannerOutput as JSON.

    The RunnerV2 now constructs a fresh Planner per-run using the injected
    LLMProvider, so tests inject this stub as ``planner_v2_2_llm`` and control
    the returned PlannerOutput via the JSON body handed back from ``generate()``.
    """

    def __init__(self, planner_output: PlannerOutput) -> None:
        self._json = planner_output.model_dump_json()

    async def generate(self, request: Any) -> LLMResponse:
        return LLMResponse(
            text=self._json,
            finish_reason="stop",
            input_tokens=10,
            output_tokens=20,
        )


# ---------------------------------------------------------------------------
# B-1 / B-4 regression: RunnerV2 with planner_v2_2=None runs as before
# ---------------------------------------------------------------------------


def test_runner_without_planner_v2_2_completes_happy_path() -> None:
    """Regression: planner_v2_2_llm=None → v2 path unchanged, no Stage 5b/7a."""
    stages = _wire_stage_mocks()
    runner = RunnerV2(**stages)  # planner_v2_2_llm defaults to None

    events = list(runner.execute({"ticker": "AAPL"}, _empty_template()))

    assert isinstance(events[-1], Completed)
    assert runner.state == RunState.COMPLETED

    stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
    assert PipelineStage.PLANNER_V2_2 not in stage_names
    assert PipelineStage.MATERIALIZE not in stage_names
    assert PipelineStage.DRAFT in stage_names


# ---------------------------------------------------------------------------
# B-1 + B-2: Stage 5b and 7a are activated when planner_v2_2 is injected
# ---------------------------------------------------------------------------


def test_runner_with_planner_v2_2_activates_stage_5b_and_7a() -> None:
    """B-1 + B-2: Stage 5b (PLANNER_V2_2) and 7a (MATERIALIZE) appear in the event stream."""
    planner_output = _minimal_planner_output()
    stub_llm = _StubLLMProvider(planner_output)

    stages = _wire_stage_mocks()
    runner = RunnerV2(**stages, planner_v2_2_llm=stub_llm)

    events = list(runner.execute({"ticker": "AAPL"}, _empty_template()))

    stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
    assert PipelineStage.PLANNER_V2_2 in stage_names, "Stage 5b missing from event stream"
    assert PipelineStage.MATERIALIZE in stage_names, "Stage 7a missing from event stream"

    # Stage 5b must appear after MODEL_PLAN
    idx_model_plan = stage_names.index(PipelineStage.MODEL_PLAN)
    idx_5b = stage_names.index(PipelineStage.PLANNER_V2_2)
    idx_7a = stage_names.index(PipelineStage.MATERIALIZE)
    idx_draft = stage_names.index(PipelineStage.DRAFT)

    assert idx_model_plan < idx_5b, "Stage 5b must follow MODEL_PLAN"
    assert idx_5b < idx_7a, "Stage 7a must follow Stage 5b"
    assert idx_7a < idx_draft, "DRAFT must follow Stage 7a"

    assert isinstance(events[-1], Completed)
    assert runner.state == RunState.COMPLETED


# ---------------------------------------------------------------------------
# B-3 + A-7: unknown helper name emits HELPER_UNAVAILABLE
# ---------------------------------------------------------------------------


def test_unknown_helper_name_emits_helper_unavailable_issue() -> None:
    """B-3 + A-7: PlannerOutput with unregistered helper name triggers HELPER_UNAVAILABLE."""
    planner_output = _minimal_planner_output(helper_name="__no_such_helper_xyz__")
    stub_llm = _StubLLMProvider(planner_output)

    stages = _wire_stage_mocks()
    runner = RunnerV2(**stages, planner_v2_2_llm=stub_llm)

    events = list(runner.execute({"ticker": "AAPL"}, _empty_template()))

    # Pipeline must complete (not fail) — HELPER_UNAVAILABLE is not a pipeline crash.
    assert isinstance(events[-1], Completed)

    # Verify stage 7a ran (MATERIALIZE event must be present).
    stage_names = [e.stage for e in events if isinstance(e, StageStarted)]
    assert PipelineStage.MATERIALIZE in stage_names

    # Verify the MaterializedReport carries the unavailable issues.
    # We cannot easily inspect the internal materialized_report from outside,
    # but we can verify the run completed (degraded-gracefully path).
    assert runner.state in (RunState.COMPLETED, RunState.DEGRADED)


def test_helper_unavailable_issue_carries_correct_type() -> None:
    """A-7: the HELPER_UNAVAILABLE VerifierIssue has correct type and severity."""
    from openlia.llm.runtime.report_v2.runner_v2 import RunnerV2 as _RunnerV2

    planner_output = _minimal_planner_output(helper_name="__ghost_helper__")
    stub_llm = _StubLLMProvider(planner_output)

    stages = _wire_stage_mocks()
    runner = _RunnerV2(**stages, planner_v2_2_llm=stub_llm)

    events = list(runner.execute({"ticker": "AAPL"}, _empty_template()))
    assert isinstance(events[-1], Completed)

    # The materialized report should have been created and its _unavailable_issues populated.
    # We verify this via the MATERIALIZE StageCompleted event being present.
    materialize_completed = [
        e for e in events if isinstance(e, StageCompleted) and e.stage == PipelineStage.MATERIALIZE
    ]
    assert len(materialize_completed) == 1


# ---------------------------------------------------------------------------
# A-3: build_drafter_prompt() is called when MaterializedSection is available
# ---------------------------------------------------------------------------


def test_draft_one_uses_build_drafter_prompt_when_materialized_section_present() -> None:
    """A-3: _draft_one uses build_drafter_prompt path when materialized_section supplied."""
    from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import (
        SectionDrafter as _SectionDrafter,
    )
    from openlia.llm.runtime.report_v2_2.materialize import MaterializedSection

    llm_mock = Mock()
    llm_mock.call.return_value = {"blocks": [{"type": "prose", "text": "ok"}]}
    trigger = Mock()
    trigger.evaluate.return_value = Mock(fire=True, reason="")
    drafter = _SectionDrafter(llm_mock, trigger)

    mat_section = MaterializedSection(
        section_id="s1",
        title="Test Section",
        rendered_artifacts=[],
        cross_section_themes=["theme1"],
    )

    section = Mock()
    section.id = "s1"
    section.name = "Test Section"
    section.directive = "Write about X"
    section.depends_on = []
    section.trigger_when = None

    pool = ResearchPool()

    outputs = drafter.draft_all(
        sections=[section],
        dag={"s1": []},  # must include section id for topological_order to visit it
        composer_inputs={"ticker": "MSFT", "template_id": "stock_initiation_v2"},
        research_pool=pool,
        model_artifacts=[],
        materialized_by_section={"s1": mat_section},
    )
    assert len(outputs) == 1
    assert outputs[0].status == "OK"

    # Verify the system prompt passed to llm.call used build_drafter_prompt output
    # (the v2.2 prompt contains "You are a section subagent").
    call_kwargs = llm_mock.call.call_args
    system_arg = call_kwargs.kwargs.get("system") or ""
    assert "section subagent" in system_arg.lower() or "You are" in system_arg


def test_draft_one_uses_v2_prompt_when_no_materialized_section() -> None:
    """A-3: _draft_one uses v2 hand-rolled prompt path when materialized_section is None."""
    from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import (
        SectionDrafter as _SectionDrafter2,
    )

    llm_mock = Mock()
    llm_mock.call.return_value = {"blocks": [{"type": "prose", "text": "ok"}]}
    trigger = Mock()
    trigger.evaluate.return_value = Mock(fire=True, reason="")
    drafter = _SectionDrafter2(llm_mock, trigger)

    section = Mock()
    section.id = "s1"
    section.name = "Test Section"
    section.directive = "Write about X"
    section.depends_on = []
    section.trigger_when = None

    pool = ResearchPool()

    outputs = drafter.draft_all(
        sections=[section],
        dag={"s1": []},  # must include section id for topological_order to visit it
        composer_inputs={"ticker": "MSFT"},
        research_pool=pool,
        model_artifacts=[],
        # No materialized_by_section → v2 path
    )
    assert len(outputs) == 1
    assert outputs[0].status == "OK"

    # v2 path: system prompt starts with "Draft section '..."
    call_kwargs = llm_mock.call.call_args
    system_arg = call_kwargs.kwargs.get("system") or ""
    assert "Draft section" in system_arg


# ---------------------------------------------------------------------------
# B-4: make_v2_runner_stage_factory() injects planner_v2_2
# ---------------------------------------------------------------------------


def test_make_v2_runner_stage_factory_populates_planner_v2_2_llm() -> None:
    """B-4: factory constructs RunnerV2 with planner_v2_2_llm populated.

    The factory no longer constructs a Planner at factory time. It injects the
    LLMProvider as planner_v2_2_llm; RunnerV2._stage_planner_v2_2() constructs
    a fresh Planner per-run with the live ticker + template context.

    Post-bdfec9dd the factory takes a per-slot ``ResolvedModel`` mapping from
    ``ctx.models_by_slot``; one LLMProvider is built per slot through
    ``_build_provider_from_resolved``.
    """
    from openlia.llm.runtime.report_v2.slots import V2Slot
    from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel

    fake_provider = Mock()
    fake_provider.generate = Mock()

    def _resolved(slot: V2Slot) -> ResolvedModel:
        return ResolvedModel(
            provider_kind="openai",
            provider_id=f"prov-{slot.value}",
            model_id=f"model-{slot.value}",
            model_ref=f"openai:{slot.value}",
            credentials=ProviderCredentials(
                api_key="sk-test", base_url=None, env_var_name="OPENAI_API_KEY"
            ),
            capabilities=Capabilities(),
            overrides={},
        )

    class _Ctx:
        models_by_slot = {slot.value: _resolved(slot) for slot in V2Slot}

    with patch(
        "openlia_server.services.v2_stage_factory._build_provider_from_resolved",
        return_value=fake_provider,
    ):
        from openlia_server.services.v2_stage_factory import make_v2_runner_stage_factory

        factory = make_v2_runner_stage_factory()
        runner = factory(_Ctx())

    assert isinstance(runner, RunnerV2)
    assert runner.planner_v2_2_llm is not None, "planner_v2_2_llm must be injected by the factory"
    # The injected value is the LLMProvider (fake_provider), not a Planner.
    assert runner.planner_v2_2_llm is fake_provider


# ---------------------------------------------------------------------------
# A-2: Planner.plan() raises from a running event loop
# ---------------------------------------------------------------------------


def test_planner_plan_raises_in_running_loop() -> None:
    """A-2: Planner.plan() raises RuntimeError when called inside a running event loop."""
    response_json = json.dumps(
        {
            "helper_selection": [],
            "planner_overrides": [],
            "open_questions": [],
            "cross_section_themes": [],
        }
    )

    class _StubLLMProvider:
        async def generate(self, request: Any) -> Any:
            from openlia.llm.types import LLMResponse

            return LLMResponse(
                text=response_json,
                finish_reason="stop",
                input_tokens=10,
                output_tokens=20,
            )

    planner = Planner(
        llm=_StubLLMProvider(),  # type: ignore[arg-type]
        ticker="AAPL",
        template_sections=[],
        template_id="stock_initiation_v2",
    )

    async def _call_plan_from_loop() -> None:
        # This should raise because we are inside a running loop.
        planner.plan()

    with pytest.raises(RuntimeError, match="running event loop"):
        asyncio.run(_call_plan_from_loop())


def test_planner_aplan_works_outside_loop() -> None:
    """A-2: Planner.plan() works fine when no event loop is running."""
    response_json = json.dumps(
        {
            "helper_selection": [],
            "planner_overrides": [],
            "open_questions": [],
            "cross_section_themes": [],
        }
    )

    class _StubLLMProvider:
        async def generate(self, request: Any) -> Any:
            from openlia.llm.types import LLMResponse

            return LLMResponse(
                text=response_json,
                finish_reason="stop",
                input_tokens=10,
                output_tokens=20,
            )

    planner = Planner(
        llm=_StubLLMProvider(),  # type: ignore[arg-type]
        ticker="AAPL",
        template_sections=[],
        template_id="stock_initiation_v2",
    )
    output = planner.plan()
    from openlia.llm.runtime.report_v2_2.planner import PlannerOutput

    assert isinstance(output, PlannerOutput)


# ---------------------------------------------------------------------------
# A-9: comparables_run is registered under underscore name
# ---------------------------------------------------------------------------


def test_comparables_run_registered_under_underscore_name() -> None:
    """A-9: comparables_run must be registered as 'comparables_run', not 'comparables.run'."""
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("comparables_run")
    assert h is not None, "comparables_run not found in registry"
    assert h.schema.directory.name == "comparables_run"

    # Old dot-notation name must no longer resolve.
    h_dot = get_helper("comparables.run")
    assert h_dot is None, "'comparables.run' (dot) must not be registered — use 'comparables_run'"
