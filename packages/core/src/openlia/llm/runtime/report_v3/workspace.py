"""In-flight run state for a v3 run.

A ``RunWorkspace`` holds what the model has produced so far —
sections written, charts emitted, and the citation ledger. The
runner threads one workspace through the entire loop; tools mutate
it directly. At finalize the workspace renders to a ``RunResult``.

Separated from ``runner.py`` so output tools (``write_section``,
``emit_chart``, ``finalize``) can hold a reference without importing
the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ledger import CitationLedger
from .schemas import ChartSpec, RunResult, TemplateSpec


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

    def required_section_ids(self) -> list[str]:
        return [section.id for section in self.template.sections]

    def missing_section_ids(self) -> list[str]:
        return [sid for sid in self.required_section_ids() if sid not in self.sections]

    def to_result(self, *, status: str, message: str = "") -> RunResult:
        ordered_sections = []
        for spec in self.template.sections:
            section = self.sections.get(spec.id)
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
        )
