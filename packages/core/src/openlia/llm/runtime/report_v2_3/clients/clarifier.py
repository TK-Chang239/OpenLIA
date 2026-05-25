"""Client protocol for the CLARIFY stage.

A `ClarifierClient` takes a raw user prompt + a small amount of run context
and returns a `ClarifyResult` (`ClarifyProceed | ClarifyNeedsInput`). The
real implementation calls the Anthropic SDK with a clarifier prompt; tests
inject `FakeClarifierClient` with a canned result.

The client itself is stateless. The stage owns the decision of whether to
suspend (on `needs_input`) or finalize (on resume with `clarify_answers`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import ClarifyResult, Language, ReportType
from ..templates import TemplateSpec


@dataclass(slots=True)
class ClarifierRequest:
    """Input passed to the clarifier LLM call."""

    raw_prompt: str
    language: Language
    report_type: ReportType
    tickers: list[str]
    template: TemplateSpec


class ClarifierClient(Protocol):
    """Maps a clarifier request to a discriminated ClarifyResult."""

    def clarify(self, request: ClarifierRequest) -> ClarifyResult: ...


class FakeClarifierClient(ClarifierClient):
    """Test fake. Supply either a fixed `result` or a callable to vary
    behavior across calls (e.g. suspend the first call, proceed on the
    second)."""

    def __init__(
        self,
        result: ClarifyResult | None = None,
        responder: Callable[[ClarifierRequest], ClarifyResult] | None = None,
    ) -> None:
        if (result is None) == (responder is None):
            raise ValueError("Provide exactly one of `result` or `responder`.")
        self._result = result
        self._responder = responder
        self.calls: list[ClarifierRequest] = []

    def clarify(self, request: ClarifierRequest) -> ClarifyResult:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._result is not None
        return self._result
