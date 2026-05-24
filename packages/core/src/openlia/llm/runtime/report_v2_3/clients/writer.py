"""Client protocol for the WRITE stage.

One `WriterClient` call produces one `WrittenSection` for one
`SectionMandate`. The stage drives all sections from the same thesis so
they cohere; the client itself is single-section.

On a VERIFY-triggered retry, the stage passes `prior_attempt` + the
HIGH-severity `critique` so the writer can target the rewrite instead of
starting from scratch.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import (
    BundleFact,
    ChartSpec,
    Language,
    ReportLength,
    ReportThesis,
    SectionMandate,
    VerifyIssue,
    WrittenSection,
)


@dataclass(slots=True)
class WriterRequest:
    """Input for one section's WRITE call.

    `relevant_facts` and `assigned_charts` are pre-filtered slices of the
    bundle and thesis charts — the writer should never see facts or charts
    outside its mandate, and the placeholder validators at the stage layer
    enforce that what comes back stays inside the slice.
    """

    section_mandate: SectionMandate
    thesis: ReportThesis
    language: Language
    relevant_facts: dict[str, BundleFact]
    assigned_charts: list[ChartSpec]
    length: ReportLength = ReportLength.NORMAL
    prior_attempt: WrittenSection | None = None
    critique: list[VerifyIssue] | None = None


class WriterClient(Protocol):
    def write(self, request: WriterRequest) -> WrittenSection: ...


class FakeWriterClient(WriterClient):
    """Test fake. Pass either a fixed `result` (single section reuse) or a
    `responder` callable that derives the section from the request — the
    latter is what most tests want so each mandate gets a distinct body."""

    def __init__(
        self,
        result: WrittenSection | None = None,
        responder: Callable[[WriterRequest], WrittenSection] | None = None,
    ) -> None:
        if (result is None) == (responder is None):
            raise ValueError("Provide exactly one of `result` or `responder`.")
        self._result = result
        self._responder = responder
        self.calls: list[WriterRequest] = []

    def write(self, request: WriterRequest) -> WrittenSection:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._result is not None
        return self._result
