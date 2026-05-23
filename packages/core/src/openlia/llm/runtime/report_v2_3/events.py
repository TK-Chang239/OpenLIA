"""Runner-level events emitted by ``ReportRunner`` at stage boundaries.

These events let an SSE route (or any other observer) surface live
progress while the runner walks the pipeline. The runner accepts an
optional ``observer`` callable on ``start()`` / ``resume()``; when
provided, it is invoked for every event below.

Events are tiny, pure-data Pydantic models so the route layer can
serialize them straight to SSE without an intermediate translation
table. Names line up with what a UI would label:

  - ``stage_started`` — runner is about to invoke a stage
  - ``stage_completed`` — stage returned cleanly
  - ``suspended`` — CLARIFY (or a future suspendable stage) set
    ``WAITING_ON_USER``; payload carries the pending questions
  - ``failed`` — stage raised; payload carries the error message
  - ``completed`` — ASSEMBLE finished and the run is done
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .schemas import ClarifyQuestion
from .slots import V23Slot


class StageStarted(BaseModel):
    kind: Literal["stage_started"] = "stage_started"
    slot: V23Slot


class StageCompleted(BaseModel):
    kind: Literal["stage_completed"] = "stage_completed"
    slot: V23Slot
    retry_count: int = 0


class Suspended(BaseModel):
    kind: Literal["suspended"] = "suspended"
    slot: V23Slot
    questions: list[ClarifyQuestion] = Field(default_factory=list)


class Failed(BaseModel):
    kind: Literal["failed"] = "failed"
    slot: V23Slot | None
    error: str


class Completed(BaseModel):
    kind: Literal["completed"] = "completed"


RunnerEvent = StageStarted | StageCompleted | Suspended | Failed | Completed


__all__ = [
    "Completed",
    "Failed",
    "RunnerEvent",
    "StageCompleted",
    "StageStarted",
    "Suspended",
]
