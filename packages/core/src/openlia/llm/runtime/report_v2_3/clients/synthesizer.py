"""Client protocol for the SYNTHESIZE stage.

A `SynthesizerClient` consumes the full research bundle and outline and
returns a `ReportThesis`: the coherence anchor that every writer is
conditioned on. The real implementation calls the Anthropic SDK with the
synthesis prompt; tests inject `FakeSynthesizerClient` with a canned
result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import (
    ClarifyResult,
    Language,
    Outline,
    ReportThesis,
    ResearchBundle,
)


@dataclass(slots=True)
class SynthesizerRequest:
    """Input passed to the synthesizer LLM call.

    `clarify_result` is included because the assumptions captured at CLARIFY
    (audience, horizon, report type) shape the thesis — the synthesizer must
    not invent them from scratch. The bundle and outline are the structural
    inputs; `language` controls the language the thesis must be written in.
    """

    raw_prompt: str
    language: Language
    bundle: ResearchBundle
    outline: Outline
    clarify_result: ClarifyResult | None = None


class SynthesizerClient(Protocol):
    def synthesize(self, request: SynthesizerRequest) -> ReportThesis: ...


class FakeSynthesizerClient(SynthesizerClient):
    """Test fake. Provide a fixed `result` or a `responder` callable that
    derives the thesis from the request (e.g. for tests that exercise the
    request-passthrough wiring)."""

    def __init__(
        self,
        result: ReportThesis | None = None,
        responder: Callable[[SynthesizerRequest], ReportThesis] | None = None,
    ) -> None:
        if (result is None) == (responder is None):
            raise ValueError("Provide exactly one of `result` or `responder`.")
        self._result = result
        self._responder = responder
        self.calls: list[SynthesizerRequest] = []

    def synthesize(self, request: SynthesizerRequest) -> ReportThesis:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._result is not None
        return self._result
