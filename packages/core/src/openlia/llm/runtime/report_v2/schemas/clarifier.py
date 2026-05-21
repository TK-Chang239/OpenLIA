"""Clarifier output schemas for Stage 1 (Task P1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClarifyingQuestion(BaseModel):
    id: str
    text: str
    kind: Literal["multiple_choice", "free_text"]
    options: list[str] | None = None


class CapabilityWarning(BaseModel):
    capability_id: str
    detected_phrase: str
    user_message: str
    available_actions: list[Literal["proceed_without", "cancel_and_edit", "clarify"]] = Field(
        default_factory=lambda: ["proceed_without", "cancel_and_edit", "clarify"]
    )


class ClarifierOutput(BaseModel):
    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    blocking_warnings: list[CapabilityWarning] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    detected_intents: list[str] = Field(default_factory=list)
