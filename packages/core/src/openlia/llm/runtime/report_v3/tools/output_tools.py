"""Output tools — the model's only path to producing report content.

Three tools:

- ``write_section(section_id, markdown)`` — append/replace a section.
  Validates every ``[^source_id]`` citation marker against the ledger;
  unresolved markers come back as a structured error and the model
  re-emits. Last write per section_id wins.

- ``emit_chart(chart_id, chart_type, title, data, axes, source_ids)``
  — register a chart spec keyed by ``chart_id``. The model references
  it from section markdown via ``{{chart:<chart_id>}}``. Lean Pydantic
  validation with permissive coercion. Invalid specs come back as
  error for the model to fix.

- ``finalize()`` — signal completion. If any required template section
  is unwritten, returns ``{"missing_sections": [...]}`` so the model
  knows what to do; otherwise marks the workspace finalized and the
  runner exits the loop.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
)
from ...report_v2_3.schemas import ComputedSource
from ..schemas import ChartSpec
from ..workspace import RunWorkspace, WrittenSection

CITATION_MARKER_RE = re.compile(r"\[\^([a-z0-9_]+)\]")


def build_output_tools(*, workspace: RunWorkspace) -> list[ResearchTool]:
    """Return write_section + emit_chart + finalize tools."""
    return [
        _build_write_section_tool(workspace),
        _build_emit_chart_tool(workspace),
        _build_finalize_tool(workspace),
    ]


# ---------------------------------------------------------------------------
# write_section
# ---------------------------------------------------------------------------


def _build_write_section_tool(workspace: RunWorkspace) -> ResearchTool:
    template_section_titles = {s.id: s.title for s in workspace.template.sections}

    def _resolve_title(section_id: str) -> str:
        """Title for the persisted section. Template ids carry their
        canonical title; revise-mode-added section ids title-case the
        slug (``competitor_landscape`` → ``Competitor Landscape``).
        Callers can override via the ``title`` arg if they want a
        different display string."""
        if section_id in template_section_titles:
            return template_section_titles[section_id]
        return section_id.replace("_", " ").title()

    def _execute(args: dict[str, Any]) -> ToolResult:
        section_id = str(args.get("section_id", "")).strip()
        markdown = args.get("markdown", "")
        if not section_id:
            raise ToolExecutionError("write_section requires `section_id`.")
        # In revise mode, the user-locked design allows the engine to
        # add sections beyond the template (the template is a
        # starting point). In original-run mode, section_id must be
        # one of the template's ids — straying outside is rejected so
        # the run can't render an incoherent shape.
        if not workspace.revision_mode and section_id not in template_section_titles:
            raise ToolExecutionError(
                f"Unknown section_id {section_id!r}. "
                f"Valid ids: {sorted(template_section_titles)}."
            )
        if not isinstance(markdown, str) or not markdown.strip():
            raise ToolExecutionError(
                "write_section requires non-empty string `markdown`."
            )

        unresolved = _unresolved_citations(markdown, workspace)
        if unresolved:
            valid_ids = [e.source_id for e in workspace.ledger.all()]
            raise ToolExecutionError(
                f"Unresolved citations in section {section_id!r}: {unresolved}. "
                f"Valid source_ids in the ledger: {valid_ids}. "
                f"Re-emit the section using only ledger source_ids."
            )

        unresolved_charts = _unresolved_chart_refs(markdown, workspace)
        if unresolved_charts:
            valid_charts = sorted(workspace.charts)
            raise ToolExecutionError(
                f"Unknown chart refs in section {section_id!r}: {unresolved_charts}. "
                f"Available charts: {valid_charts}. "
                f"Emit the missing charts via emit_chart first."
            )

        workspace.sections[section_id] = WrittenSection(
            section_id=section_id,
            title=_resolve_title(section_id),
            markdown=markdown,
        )
        workspace.note_section_written(section_id)
        return ToolResult(
            payload={
                "ok": True,
                "section_id": section_id,
                "char_count": len(markdown),
                "missing_sections": workspace.missing_section_ids(),
            },
            provenance=ComputedSource(method="write_section", derived_from=["(workspace)"]),
            summary=f"Wrote section {section_id} ({len(markdown)} chars).",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="write_section",
            description=(
                "Write (or rewrite) one section of the report. `markdown` "
                "uses standard Markdown plus inline citation markers like "
                "`[^web_3]` or `[^eodhd_1]` for every numeric or factual "
                "claim. Reference previously-emitted charts with "
                "`{{chart:<chart_id>}}`. Unresolved citation or chart "
                "references come back as an error; fix and re-emit."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": (
                            "One of the template's section ids. See the system "
                            "prompt for the full list."
                        ),
                    },
                    "markdown": {
                        "type": "string",
                        "description": "Section body in Markdown.",
                    },
                },
                "required": ["section_id", "markdown"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _unresolved_citations(markdown: str, workspace: RunWorkspace) -> list[str]:
    ids = set(CITATION_MARKER_RE.findall(markdown))
    return sorted(sid for sid in ids if workspace.ledger.lookup(sid) is None)


_CHART_REF_RE = re.compile(r"\{\{chart:([a-z0-9_]+)\}\}")


def _unresolved_chart_refs(markdown: str, workspace: RunWorkspace) -> list[str]:
    ids = set(_CHART_REF_RE.findall(markdown))
    return sorted(cid for cid in ids if cid not in workspace.charts)


# ---------------------------------------------------------------------------
# emit_chart
# ---------------------------------------------------------------------------


def _build_emit_chart_tool(workspace: RunWorkspace) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            spec = ChartSpec.model_validate(args)
        except ValidationError as exc:
            raise ToolExecutionError(
                f"Invalid chart spec: {exc.errors(include_url=False, include_context=False)}"
            ) from exc

        unresolved = [
            sid for sid in spec.source_ids if workspace.ledger.lookup(sid) is None
        ]
        if unresolved:
            valid = [e.source_id for e in workspace.ledger.all()]
            raise ToolExecutionError(
                f"Chart {spec.chart_id!r} references unknown source_ids: {unresolved}. "
                f"Valid source_ids: {valid}."
            )

        workspace.charts[spec.chart_id] = spec
        workspace.note_chart_written(spec.chart_id)
        return ToolResult(
            payload={
                "ok": True,
                "chart_id": spec.chart_id,
                "reference": f"{{{{chart:{spec.chart_id}}}}}",
            },
            provenance=ComputedSource(method="emit_chart", derived_from=["(workspace)"]),
            summary=f"Emitted chart {spec.chart_id} ({spec.chart_type}).",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="emit_chart",
            description=(
                "Register a chart spec. Reference it later from any "
                "section's markdown via `{{chart:<chart_id>}}`. "
                "Allowed chart types: line, bar, column, area, pie, "
                "scatter, table. Cite the data sources via `source_ids` "
                "(each must already exist in the ledger)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "chart_id": {
                        "type": "string",
                        "description": "Slug used to reference the chart from markdown.",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["line", "bar", "column", "area", "pie", "scatter", "table"],
                    },
                    "title": {"type": "string"},
                    "data": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "description": (
                                "Each item carries either {label, value} for "
                                "categorical charts or {x, y} for scatter/line."
                            ),
                        },
                    },
                    "axes": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Optional axis labels, e.g. "
                            "{x: 'Fiscal Year', y: 'Revenue ($B)'}."
                        ),
                    },
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ledger source_ids the chart data draws from.",
                    },
                },
                "required": ["chart_id", "chart_type", "title", "data"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------


def _build_finalize_tool(workspace: RunWorkspace) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        missing = workspace.missing_section_ids()
        if missing:
            return ToolResult(
                payload={
                    "ok": False,
                    "missing_sections": missing,
                    "message": (
                        "Some required template sections are not yet written. "
                        "Call write_section for each missing id, then call "
                        "finalize() again."
                    ),
                },
                provenance=ComputedSource(method="finalize", derived_from=["(workspace)"]),
                summary=f"finalize blocked: {len(missing)} missing sections.",
            )

        # Revise mode: at least one section must have been touched
        # this run — finalizing a revision that wrote nothing would
        # produce a confusing no-op revision row + version bump.
        if (
            workspace.revision_mode
            and not workspace.sections_written_this_run
        ):
            return ToolResult(
                payload={
                    "ok": False,
                    "message": (
                        "Revisions must write at least one section. Call "
                        "write_section for the sections you want to revise "
                        "(or add), then call finalize() again."
                    ),
                },
                provenance=ComputedSource(method="finalize", derived_from=["(workspace)"]),
                summary="finalize blocked: revision wrote no sections.",
            )

        workspace.finalized = True
        return ToolResult(
            payload={
                "ok": True,
                "sections_written": len(workspace.sections),
                "charts_emitted": len(workspace.charts),
                "citations_logged": len(workspace.ledger),
            },
            provenance=ComputedSource(method="finalize", derived_from=["(workspace)"]),
            summary="Run finalized.",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="finalize",
            description=(
                "Signal that the report is complete. Returns "
                "`{missing_sections: [...]}` if any required template "
                "section is still unwritten; otherwise marks the run done "
                "and the loop exits."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )
