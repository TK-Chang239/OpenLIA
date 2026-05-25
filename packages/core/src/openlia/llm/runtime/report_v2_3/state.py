"""ReportState — the typed checkpoint owned by ReportRunner.

The runner is a suspendable state machine: CLARIFY can hand control back to
the user mid-run. On `needs_input` the runner persists this state, sets
WAITING_ON_USER, and returns. A resume entry point loads the state and
continues from `current_stage`. Every stage reads a slice of state and writes
a slice — there is no free-floating prose between stages.

Pydantic-native so persistence is `state.model_dump_json()` into a JSONB column
keyed by `run_id`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .schemas import (
    ClarifyAnswers,
    ClarifyQuestion,
    ClarifyResult,
    Language,
    Outline,
    ReportLength,
    ReportThesis,
    ReportType,
    ResearchBundle,
    ResolvedReport,
    RunStatus,
    VerifyResult,
    WrittenSection,
)
from .slots import V23Slot
from .templates import TemplateSpec


def _now() -> datetime:
    return datetime.now(UTC)


class ReportState(BaseModel):
    """Single typed checkpoint for one report run.

    - `current_stage` tracks pipeline position so resume() picks up correctly.
    - `pending_questions` is populated only when status == WAITING_ON_USER.
    - Stage outputs (outline, bundle, thesis, ...) accumulate as the pipeline
      advances. None means "not yet produced".
    - `retry_count` is the verify->write bounded retry counter (max 1).
    """

    # Identity ---------------------------------------------------------------
    run_id: str
    user_id: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Inputs -----------------------------------------------------------------
    raw_prompt: str
    language: Language
    report_type: ReportType
    # Structural source of truth for this run — section list, intents,
    # methodology hints. The wiring layer supplies it from
    # `get_builtin(report_type)` when no user template is selected.
    # Required, no default: every run carries a template.
    template: TemplateSpec
    length: ReportLength = ReportLength.NORMAL
    # Optional reference to a user-uploaded report template (UUID from
    # the report_templates table). When set, the planner uses the
    # template's section plan instead of the built-in section list for
    # `report_type`. Built-in templates correspond 1:1 to the
    # `ReportType` enum members and are selected by leaving this None.
    template_id: str | None = None
    # Subject tickers. Allowed to start empty when the run was kicked
    # off through the single-textarea composer; CLARIFY then extracts
    # them from `raw_prompt` and copies `inferred_tickers` here before
    # PLAN. Stages downstream of CLARIFY may continue to assume this
    # is non-empty.
    tickers: list[str] = Field(default_factory=list)
    model_assignments: dict[V23Slot, str] = Field(
        default_factory=dict,
        description="V23Slot -> stored model_id; resolver expands to ResolvedModel at call time.",
    )

    # Runtime control --------------------------------------------------------
    status: RunStatus = RunStatus.RUNNING
    current_stage: V23Slot | None = None
    retry_count: int = 0
    last_error: str | None = None

    # Suspend / resume -------------------------------------------------------
    pending_questions: list[ClarifyQuestion] = Field(default_factory=list)
    clarify_answers: ClarifyAnswers | None = None

    # Stage outputs (filled progressively) -----------------------------------
    clarify_result: ClarifyResult | None = None
    outline: Outline | None = None
    bundle: ResearchBundle | None = None
    thesis: ReportThesis | None = None
    sections: list[WrittenSection] = Field(default_factory=list)
    verify_result: VerifyResult | None = None
    resolved: ResolvedReport | None = None

    # ------------------------------------------------------------------
    # mutation helpers — the runner uses these so updated_at stays fresh
    # ------------------------------------------------------------------
    def touch(self) -> None:
        self.updated_at = _now()

    def suspend_for_clarify(self, questions: list[ClarifyQuestion]) -> None:
        self.status = RunStatus.WAITING_ON_USER
        self.pending_questions = list(questions)
        self.touch()

    def resume_with_answers(self, answers: ClarifyAnswers) -> None:
        self.clarify_answers = answers
        self.pending_questions = []
        self.status = RunStatus.RUNNING
        self.touch()

    def fail(self, message: str) -> None:
        self.status = RunStatus.FAILED
        self.last_error = message
        self.touch()

    def complete(self) -> None:
        self.status = RunStatus.COMPLETE
        self.touch()
