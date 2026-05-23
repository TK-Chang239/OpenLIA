"""Construction of the v2.3 ReportRunner for a single request.

Real stages are wired in progressively as the engine PRs land. Today:

- CLARIFY: real, requires `clarifier_client`.
- PLAN: real when `planner_client` is supplied; NoOp otherwise.
- SYNTHESIZE: real when `synthesizer_client` is supplied; NoOp otherwise.
- WRITE: real when `writer_client` is supplied; NoOp otherwise.
- ASSEMBLE: real by default — no LLM client needed. Falls back to a
  graceful no-op on `state` when upstream stages have not populated
  sections/bundle/thesis/outline, so the factory works for both
  fully-wired runs and partially-NoOp runs.
- Everything else (RESEARCH, COMPUTE, VISUALIZE, VERIFY): still NoOp,
  swapped in subsequent PRs.

A `V23RunnerFactory` is a callable held on `app.state.v2_3_runner_factory`
that the route layer invokes per request to build a `ReportRunner`. The
factory captures its client dependencies so tests can substitute fakes
without touching the route layer.
"""

from __future__ import annotations

from collections.abc import Callable

from openlia.llm.runtime.report_v2_3.clients.clarifier import ClarifierClient
from openlia.llm.runtime.report_v2_3.clients.planner import PlannerClient
from openlia.llm.runtime.report_v2_3.clients.synthesizer import SynthesizerClient
from openlia.llm.runtime.report_v2_3.clients.writer import WriterClient
from openlia.llm.runtime.report_v2_3.runner import ReportRunner
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.stages import (
    PIPELINE_ORDER,
    ClarifyStage,
    NoOpStage,
    PlanStage,
    RealAssembleStage,
    Stage,
    StageContext,
    SynthesizeStage,
    WriteStage,
)

V23RunnerFactory = Callable[[], ReportRunner]


def make_v2_3_runner_factory(
    clarifier_client: ClarifierClient,
    *,
    planner_client: PlannerClient | None = None,
    synthesizer_client: SynthesizerClient | None = None,
    writer_client: WriterClient | None = None,
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
        if synthesizer_client is not None:
            stages[V23Slot.SYNTHESIZE] = SynthesizeStage(synthesizer_client)
        if writer_client is not None:
            stages[V23Slot.WRITE] = WriteStage(writer_client)
        return ReportRunner(
            stages=stages,
            assemble=RealAssembleStage(),
            ctx=StageContext(clients={}, tools={}, extras={}),
        )

    return _factory
