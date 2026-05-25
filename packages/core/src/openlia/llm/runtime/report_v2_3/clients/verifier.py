"""Client protocol for the VERIFY stage.

A `VerifierClient` reads the full set of drafted sections + the research
bundle + the thesis and returns a `VerifyResult` listing issues. The
runner gates on `VerifyResult.must_rewrite` — any HIGH-severity issue
routes the offending section(s) back to WRITE with the critique
attached, bounded to one retry.

The verifier's hardest checks are *coherence* (cross-section
contradiction, redundancy) and *value-match* (prose number vs cited
fact value). Dangling references and structural defects are caught
deterministically by VerifyStage before the client is invoked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import (
    Language,
    ReportThesis,
    ResearchBundle,
    VerifyResult,
    WrittenSection,
)
from ..templates import TemplateSpec


@dataclass(slots=True)
class VerifierRequest:
    raw_prompt: str
    language: Language
    thesis: ReportThesis
    bundle: ResearchBundle
    sections: list[WrittenSection]
    # Phase 1 pass-through: carried for symmetry across all stage Requests
    # so callers do not have to special-case which stages consume the
    # template. Phase 3 will start using it for coverage checks.
    template: TemplateSpec


class VerifierClient(Protocol):
    def verify(self, request: VerifierRequest) -> VerifyResult: ...


class FakeVerifierClient(VerifierClient):
    """Test fake. Provide a fixed `result` or a `responder` to vary
    behavior across calls — the verify-retry loop needs the second call
    to come back clean after the first emits issues."""

    def __init__(
        self,
        result: VerifyResult | None = None,
        responder: Callable[[VerifierRequest], VerifyResult] | None = None,
    ) -> None:
        if (result is None) == (responder is None):
            raise ValueError("Provide exactly one of `result` or `responder`.")
        self._result = result
        self._responder = responder
        self.calls: list[VerifierRequest] = []

    def verify(self, request: VerifierRequest) -> VerifyResult:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._result is not None
        return self._result
