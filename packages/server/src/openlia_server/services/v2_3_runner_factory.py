"""Construction of the v2.3 ReportRunner for a single request.

For PR3, CLARIFY is the only real stage; the remaining seven slots and the
ASSEMBLE step are NoOp stages so the runner's suspend/resume control flow
can be exercised end-to-end without depending on stages that don't yet
exist. Subsequent PRs will swap NoOps for real implementations one at a
time.

A `V23RunnerFactory` is a callable held on `app.state.v2_3_runner_factory`
that the route layer invokes per request to build a `ReportRunner`. The
clarifier client is injected here so tests can substitute
`FakeClarifierClient` without touching the route layer.
"""

from __future__ import annotations

from collections.abc import Callable

from openlia.llm.runtime.report_v2_3.clients.clarifier import ClarifierClient
from openlia.llm.runtime.report_v2_3.runner import ReportRunner
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.stages import (
    PIPELINE_ORDER,
    ClarifyStage,
    NoOpAssembleStage,
    NoOpStage,
    StageContext,
)

V23RunnerFactory = Callable[[], ReportRunner]


def make_v2_3_runner_factory(clarifier_client: ClarifierClient) -> V23RunnerFactory:
    """Return a factory that builds a fresh ReportRunner per call.

    The returned callable is stateless beyond its captured dependencies; it
    can be shared across requests safely.
    """

    def _factory() -> ReportRunner:
        stages: dict[V23Slot, NoOpStage | ClarifyStage] = {
            slot: NoOpStage(slot) for slot in PIPELINE_ORDER
        }
        stages[V23Slot.CLARIFY] = ClarifyStage(clarifier_client)
        return ReportRunner(
            stages=stages,
            assemble=NoOpAssembleStage(),
            ctx=StageContext(clients={}, tools={}, extras={}),
        )

    return _factory
