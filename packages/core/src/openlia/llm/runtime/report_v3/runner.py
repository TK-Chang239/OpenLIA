"""Top-level runner for v3 equity-research runs.

Phase 0 ships the runner shell — it validates the request, opens a
session through the capability gate, attaches a fresh ledger, and
returns a placeholder ``RunResult``. Phase 1 fills in the tool-use
loop; Phase 2 wires persistence and rendering. Keeping the shell
deliberately small for Phase 0 lets the server route and tests
exercise the construction path without any LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ledger import CitationLedger
from .schemas import RunRequest, RunResult
from .session import LLMSession


@dataclass(frozen=True)
class Runner:
    """A v3 run executor.

    Stateless across runs — each ``run()`` call constructs its own
    session and ledger from the request. The instance only exists so
    Phase 1 has a place to attach configuration (max turns, timeouts)
    without changing call sites.
    """

    max_turns: int = 60
    max_wall_time_seconds: int = 15 * 60

    async def run(self, request: RunRequest) -> RunResult:
        """Execute a v3 run for the given request.

        Phase 0 behavior: opens a session (which runs the capability
        gate), creates an empty ledger, returns a placeholder result.
        Capability gate failures propagate as ``CapabilityError`` so the
        server route can surface them as 400-level responses.
        """
        session = LLMSession.create(
            provider_kind=request.provider_kind,
            model=request.model,
        )
        ledger = CitationLedger()
        # Ledger is unused in Phase 0 — the local binding documents
        # that the runner owns ledger lifecycle, which matters once
        # Phase 1 starts appending to it inside the tool loop.
        del ledger

        return RunResult(
            status="placeholder",
            subject=request.subject,
            template_id=request.template.template_id,
            message=(
                f"v3 Phase 0 scaffolding: session opened against "
                f"{session.provider_kind}/{session.model} "
                f"(web_search_native={session.capabilities.web_search_native}). "
                f"Tool loop and rendering land in Phase 1."
            ),
        )
