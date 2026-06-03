"""In-flight run state for a Macro Research dashboard run.

A ``RunWorkspace`` holds what the model has produced so far —
sections written, charts emitted, the citation ledger, and the typed
dashboard payload. The runner threads one workspace through the entire
loop; tools mutate it directly. When the model calls ``emit_dashboard``
the payload is stored and ``finalized`` is set, ending the loop.

Separated from ``runner.py`` so output tools can hold a reference
without importing the loop.

The section/chart/cover fields (``sections``, ``charts``, ``cover``,
``section_order``, etc.) are vestigial fork carry-over from the
Morning Briefing / EU v2 engines — the dashboard engine does not use
them, but they remain pending a later cleanup pass.

The engine has no revision flow: every run is an original run. The
``revision_mode`` field is always ``False``; it is vestigial, pending
cleanup (see below).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from .ledger import CitationLedger
from .schemas import ChartSpec, CoverSpec, RunResult, TemplateSpec


@dataclass
class WrittenSection:
    """One section the model has finalized via ``write_section``."""

    section_id: str
    title: str
    markdown: str


@dataclass
class RunWorkspace:
    """Mutable run state shared between the runner and the output tools."""

    template: TemplateSpec | None
    ledger: CitationLedger
    subject: str
    # Identifies the dashboard this run produces (e.g. "debt_cycle"). Used
    # as the template_id surrogate in to_result when there is no template.
    dashboard_slug: str | None = None
    sections: dict[str, WrittenSection] = field(default_factory=dict)
    charts: dict[str, ChartSpec] = field(default_factory=dict)
    finalized: bool = False
    # Always ``False``; vestigial, pending cleanup. The dashboard engine
    # has no revision flow. Retained only because the forked output tools
    # still read it as a guard; the engine never sets it to ``True``.
    revision_mode: bool = False
    # Ordered list of section_ids the renderer / to_result should
    # emit. Pre-populated with template section ids in template order;
    # ``note_section_written`` appends any genuinely new id in the
    # order it is first written.
    section_order: list[str] = field(default_factory=list)
    # The subset of ``sections`` / ``charts`` that this run wrote.
    # Carried over from v3's persistence bookkeeping.
    sections_written_this_run: set[str] = field(default_factory=set)
    charts_written_this_run: set[str] = field(default_factory=set)
    # Cover hero content from the model's ``set_cover`` tool call.
    # None until the model emits one; last write wins if it calls
    # ``set_cover`` more than once. The renderer surfaces this on the
    # v1 ReportCover via the detail adapter.
    cover: CoverSpec | None = None
    cover_written_this_run: bool = False
    # The typed dashboard payload emitted via ``emit_dashboard`` (e.g.
    # ``DebtCycleData``). None until the model emits one. Setting it
    # finalizes the run.
    payload: BaseModel | None = None

    def __post_init__(self) -> None:
        if not self.section_order and self.template is not None:
            self.section_order = [s.id for s in self.template.sections]

    def required_section_ids(self) -> list[str]:
        if self.template is None:
            return []
        return [section.id for section in self.template.sections]

    def missing_section_ids(self) -> list[str]:
        # ``revision_mode`` is always False in EU v2, so this guard is
        # inert; kept for parity with the shared output-tool contract.
        if self.revision_mode:
            return []
        return [sid for sid in self.required_section_ids() if sid not in self.sections]

    def note_section_written(self, section_id: str) -> None:
        """Bookkeeping called by ``write_section`` after a successful
        write. Appends to ``section_order`` for genuinely new section
        ids; always records the id in this-run set."""
        if section_id not in self.section_order:
            self.section_order.append(section_id)
        self.sections_written_this_run.add(section_id)

    def note_chart_written(self, chart_id: str) -> None:
        self.charts_written_this_run.add(chart_id)

    def set_cover(self, cover: CoverSpec) -> None:
        """Replace the workspace's cover spec. Called by the
        ``set_cover`` tool; flips ``cover_written_this_run`` so the
        revision persistence layer can decide whether to overwrite the
        prior cover or keep it."""
        self.cover = cover
        self.cover_written_this_run = True

    def set_payload(self, payload: BaseModel) -> None:
        """Record the typed dashboard payload from ``emit_dashboard`` and
        finalize the run so the runner exits its loop."""
        self.payload = payload
        self.finalized = True

    def to_result(self, *, status: str, message: str = "") -> RunResult:
        ordered_sections = []
        for sid in self.section_order:
            section = self.sections.get(sid)
            if section is None:
                continue
            ordered_sections.append(
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "markdown": section.markdown,
                }
            )
        template_id = (
            self.template.template_id if self.template is not None else (self.dashboard_slug or "")
        )
        return RunResult(
            status=status,  # type: ignore[arg-type]
            subject=self.subject,
            template_id=template_id,
            message=message,
            sections=ordered_sections,
            charts=list(self.charts.values()),
            citations=self.ledger.all(),
            cover=self.cover,
            payload=(
                self.payload.model_dump(mode="json", by_alias=True)
                if self.payload is not None
                else None
            ),
        )
