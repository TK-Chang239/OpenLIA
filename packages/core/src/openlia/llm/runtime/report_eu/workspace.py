"""In-flight run state for a v3 run.

A ``RunWorkspace`` holds what the model has produced so far —
sections written, charts emitted, and the citation ledger. The
runner threads one workspace through the entire loop; tools mutate
it directly. At finalize the workspace renders to a ``RunResult``.

Separated from ``runner.py`` so output tools (``write_section``,
``emit_chart``, ``finalize``) can hold a reference without importing
the loop.

PR4 adds revise-mode awareness. When ``revision_mode=True``:
  - prior sections are pre-loaded into ``sections`` so the model
    references resolve and the rendered partial result includes
    untouched prior content
  - ``write_section`` accepts section_ids beyond the template
    (revise can add new sections per the locked design)
  - ``finalize`` accepts partial completion (revisions can touch
    just one section)
  - ``sections_written_this_run`` / ``charts_written_this_run``
    track what the engine produced this revision so the persistence
    layer can version-bump only those.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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

    template: TemplateSpec
    ledger: CitationLedger
    subject: str
    sections: dict[str, WrittenSection] = field(default_factory=dict)
    charts: dict[str, ChartSpec] = field(default_factory=dict)
    finalized: bool = False
    # Revise-mode toggles. Set by ``Runner.run`` when a ``revise``
    # context is passed; default False keeps the original-run path
    # behaviour identical.
    revision_mode: bool = False
    # Ordered list of section_ids the renderer / to_result should
    # emit. Pre-populated with template section ids in template order;
    # revise-mode adds append new ids in the order they're first
    # written. Original-run paths never mutate beyond the template
    # set so this is effectively a no-op for them.
    section_order: list[str] = field(default_factory=list)
    # The subset of ``sections`` / ``charts`` that this run wrote
    # (vs. pre-loaded from a prior revision). The persistence layer
    # reads these to know which entries need a new version row.
    sections_written_this_run: set[str] = field(default_factory=set)
    charts_written_this_run: set[str] = field(default_factory=set)
    # Cover hero content from the model's ``set_cover`` tool call.
    # None until the model emits one; last write wins if it calls
    # ``set_cover`` more than once (or during a revision). The
    # renderer surfaces this on the v1 ReportCover via the v3
    # detail adapter.
    cover: CoverSpec | None = None
    cover_written_this_run: bool = False

    def __post_init__(self) -> None:
        if not self.section_order:
            self.section_order = [s.id for s in self.template.sections]

    def required_section_ids(self) -> list[str]:
        return [section.id for section in self.template.sections]

    def missing_section_ids(self) -> list[str]:
        # Revise mode: no required sections; the user picks what to
        # touch, finalize accepts any partial.
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
        return RunResult(
            status=status,  # type: ignore[arg-type]
            subject=self.subject,
            template_id=self.template.template_id,
            message=message,
            sections=ordered_sections,
            charts=list(self.charts.values()),
            citations=self.ledger.all(),
            cover=self.cover,
        )
