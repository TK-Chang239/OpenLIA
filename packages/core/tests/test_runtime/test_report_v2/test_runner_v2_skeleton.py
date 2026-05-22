"""Skeleton tests for the v2.2 RunnerV2 stage enum + state machine."""

from __future__ import annotations

from openlia.llm.runtime.report_v2.runner_v2 import (
    PipelineStage,
    RunnerV2,
    RunState,
)


def test_pipeline_stages_in_order():
    assert [s.value for s in PipelineStage] == [
        "clarify",
        "read_template",
        "research_plan",
        "gather",
        "model_plan",
        "stage_5b_planner_v2_2",  # v2.2 helper selection
        "model_build",
        "stage_7a_materialize",  # v2.2 artifact materialization
        "draft",
        "verify",
        "assemble",
    ]


def test_run_state_includes_clarify_awaiting_user():
    assert "CLARIFY_AWAITING_USER" in {s.value for s in RunState}


def test_runner_initial_state_is_started():
    r = RunnerV2()
    assert r.state == RunState.STARTED
    assert r.current_stage is None
    assert r.outcomes == []


def test_runner_state_transitions():
    r = RunnerV2()
    r.transition(RunState.RUNNING)
    assert r.state == RunState.RUNNING


def test_runner_enters_stage():
    r = RunnerV2()
    r.enter_stage(PipelineStage.GATHER)
    assert r.current_stage == PipelineStage.GATHER
