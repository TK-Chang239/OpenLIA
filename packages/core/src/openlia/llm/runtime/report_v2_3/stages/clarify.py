"""CLARIFY stage — conditional front gate with suspend/resume.

Two entry paths through this stage:

1. First run: `state.clarify_answers` is None. The stage calls the
   clarifier client. If the client returns `ClarifyNeedsInput`, the stage
   suspends the run; the runner returns control to the caller. If it
   returns `ClarifyProceed`, the stage records it and lets the runner
   advance.

2. Resume: `state.clarify_answers` is set. The stage finalizes by emitting
   a `ClarifyProceed` whose `assumptions` capture the resolved (answer or
   default) responses. The clarifier client is NOT re-invoked — re-asking
   the model after the user has answered would defeat the purpose of the
   suspend.
"""

from __future__ import annotations

from ..clients.clarifier import ClarifierClient, ClarifierRequest
from ..schemas import (
    ClarifyNeedsInput,
    ClarifyProceed,
    ClarifyResult,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class ClarifyStage(Stage):
    slot = V23Slot.CLARIFY

    def __init__(self, client: ClarifierClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        if state.clarify_answers is not None:
            state.clarify_result = self._finalize_after_resume(state)
            return state

        result = self._client.clarify(
            ClarifierRequest(
                raw_prompt=state.raw_prompt,
                language=state.language,
                report_type=state.report_type,
                tickers=list(state.tickers),
                template=state.template,
            )
        )

        if isinstance(result, ClarifyNeedsInput):
            state.suspend_for_clarify(result.questions)
            # We DO NOT yet write clarify_result — finalize happens on resume.
            return state

        # ClarifyProceed: copy inferred tickers onto state if the run was
        # started without an explicit ticker list. The downstream stages
        # (PLAN, RESEARCH) read state.tickers and assume it's populated
        # by the time they execute.
        if not state.tickers and result.inferred_tickers:
            state.tickers = list(result.inferred_tickers)
        state.clarify_result = result
        return state

    def _finalize_after_resume(self, state: ReportState) -> ClarifyResult:
        """Turn the resumed answers into an explicit ClarifyProceed.

        Use the answer-or-default resolution from the original suspended
        questions so an unanswered question still contributes its default
        to the assumptions list. If somehow the run resumed without any
        prior `clarify_result`, treat the answers as the source of truth.

        When the suspend was caused by a missing ticker (questions with
        id == "ticker" or ids ending in "_ticker"), the resolved value is
        also copied onto `state.tickers` so PLAN/RESEARCH have a subject
        — otherwise a ticker-anchored run would resume into PLAN with
        no subject.
        """
        if state.clarify_answers is None:
            raise RuntimeError("_finalize_after_resume called without answers.")

        prior = state.clarify_result
        if isinstance(prior, ClarifyNeedsInput):
            resolved = state.clarify_answers.resolve(prior.questions)
            assumptions = [f"{qid}: {value}" for qid, value in resolved.items()]
        else:
            resolved = state.clarify_answers.answers
            assumptions = [f"{qid}: {value}" for qid, value in resolved.items()]

        if not state.tickers:
            for qid, value in resolved.items():
                if qid == "ticker" or qid.endswith("_ticker") or qid == "tickers":
                    parsed = [
                        t.strip().upper()
                        for t in value.replace(",", " ").split()
                        if t.strip()
                    ]
                    if parsed:
                        state.tickers = parsed
                        break

        return ClarifyProceed(assumptions=assumptions)
