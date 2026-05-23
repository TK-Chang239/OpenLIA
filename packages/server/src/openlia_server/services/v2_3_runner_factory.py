"""Construction of the v2.3 ReportRunner for a single request.

Real stages are wired in progressively as the engine PRs land. Today:

- CLARIFY: real, requires `clarifier_client`.
- PLAN: real when `planner_client` is supplied; NoOp otherwise.
- RESEARCH: real when `researcher_client` is supplied; NoOp otherwise.
- COMPUTE: real when `compute_client` is supplied; NoOp otherwise.
- SYNTHESIZE: real when `synthesizer_client` is supplied; NoOp otherwise.
- WRITE: real when `writer_client` is supplied; NoOp otherwise.
- VISUALIZE: real by default — deterministic chart-renderability check.
  Falls back to a graceful no-op when thesis or bundle is missing.
- VERIFY: real when `verifier_client` is supplied; NoOp otherwise.
- ASSEMBLE: real by default — no LLM client needed. Falls back to a
  graceful no-op on `state` when upstream stages have not populated
  sections/bundle/thesis/outline, so the factory works for both
  fully-wired runs and partially-NoOp runs.

A `V23RunnerFactory` is a callable held on `app.state.v2_3_runner_factory`
that the route layer invokes per request to build a `ReportRunner`. The
factory captures its client dependencies so tests can substitute fakes
without touching the route layer.
"""

from __future__ import annotations

from collections.abc import Callable

from openlia.llm.runtime.report_v2_3.clients.clarifier import ClarifierClient
from openlia.llm.runtime.report_v2_3.clients.compute import ComputeClient
from openlia.llm.runtime.report_v2_3.clients.planner import PlannerClient
from openlia.llm.runtime.report_v2_3.clients.researcher import ResearcherClient
from openlia.llm.runtime.report_v2_3.clients.synthesizer import SynthesizerClient
from openlia.llm.runtime.report_v2_3.clients.verifier import VerifierClient
from openlia.llm.runtime.report_v2_3.clients.writer import WriterClient
from openlia.llm.runtime.report_v2_3.runner import ReportRunner
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.stages import (
    PIPELINE_ORDER,
    ClarifyStage,
    ComputeStage,
    NoOpStage,
    PlanStage,
    RealAssembleStage,
    ResearchStage,
    Stage,
    StageContext,
    SynthesizeStage,
    VerifyStage,
    VisualizeStage,
    WriteStage,
)

V23RunnerFactory = Callable[[], ReportRunner]


def make_v2_3_runner_factory(
    clarifier_client: ClarifierClient,
    *,
    planner_client: PlannerClient | None = None,
    researcher_client: ResearcherClient | None = None,
    compute_client: ComputeClient | None = None,
    synthesizer_client: SynthesizerClient | None = None,
    writer_client: WriterClient | None = None,
    verifier_client: VerifierClient | None = None,
) -> V23RunnerFactory:
    """Return a factory that builds a fresh ReportRunner per call.

    The returned callable is stateless beyond its captured dependencies; it
    can be shared across requests safely.
    """

    def _factory() -> ReportRunner:
        stages: dict[V23Slot, Stage] = {slot: NoOpStage(slot) for slot in PIPELINE_ORDER}
        stages[V23Slot.CLARIFY] = ClarifyStage(clarifier_client)
        if planner_client is not None:
            stages[V23Slot.PLAN] = PlanStage(planner_client)
        if researcher_client is not None:
            stages[V23Slot.RESEARCH] = ResearchStage(researcher_client)
        if compute_client is not None:
            stages[V23Slot.COMPUTE] = ComputeStage(compute_client)
        if synthesizer_client is not None:
            stages[V23Slot.SYNTHESIZE] = SynthesizeStage(synthesizer_client)
        if writer_client is not None:
            stages[V23Slot.WRITE] = WriteStage(writer_client)
        # VISUALIZE is deterministic and always real; it gracefully no-ops
        # when thesis/bundle are absent (early-suspending runs).
        stages[V23Slot.VISUALIZE] = VisualizeStage()
        if verifier_client is not None:
            stages[V23Slot.VERIFY] = VerifyStage(verifier_client)
        return ReportRunner(
            stages=stages,
            assemble=RealAssembleStage(),
            ctx=StageContext(clients={}, tools={}, extras={}),
        )

    return _factory
