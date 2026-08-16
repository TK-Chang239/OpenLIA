"""Assemble a v3 report into one self-contained HTML document.

Pipeline per ``assemble_html``:

  1. Render every persisted ``ChartSpec`` to PNG bytes; base64-encode
     so the resulting HTML is self-contained (no external file refs,
     no static-asset server needed for PDF printing).
  2. Walk sections in template order. Rewrite ``[^source_id]`` markers
     using the display_index map (the ``{{chart:<id>}}`` markers are
     left in the text for step 4).
  3. Convert rewritten section markdown to HTML via ``markdown-it-py``
     with raw-HTML passthrough disabled, so any HTML the model wrote
     into its section text is neutralised (escaped) rather than
     rendered into the output.
  4. Substitute ``{{chart:<id>}}`` markers in the rendered HTML with
     trusted ``<figure><img>`` blocks (or a text fallback when the
     chart didn't render).
  5. Wrap with the cover block + bibliography block + a minimal CSS
     reset so the document prints cleanly through Playwright.

The output is one HTML string. The caller decides whether to ship it
as-is (the ``/html`` endpoint) or pipe it through a headless browser
to produce a PDF (the ``/pdf`` endpoint).
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .chart_renderer import RenderedChart, render_chart_png
from .citation_rewriter import (
    BibliographyEntry,
    build_bibliography,
    rewrite_section_markdown,
    strip_anthropic_citation_markup,
)

# Chart markers survive the (html-disabled) markdown render as literal
# text. A marker alone on its own line arrives as ``<p>{{chart:id}}</p>``
# (group 1); an inline marker stays bare (group 2). Match both so the
# figure can be injected after rendering without being escaped.
CHART_REF_RE = re.compile(r"<p>\s*\{\{chart:([a-z0-9_]+)\}\}\s*</p>|\{\{chart:([a-z0-9_]+)\}\}")


@dataclass(frozen=True)
class AssembledReport:
    """Output of ``assemble_html``."""

    html: str
    chart_data_urls_by_id: dict[str, str]
    bibliography: list[BibliographyEntry]


def assemble_html(
    *,
    report,
    sections,
    charts,
    citations,
    now: datetime | None = None,
) -> AssembledReport:
    """Produce one self-contained HTML document for a v3 run.

    ``report`` is a ``ReportV3`` row (read-only attribute access).
    ``sections`` / ``charts`` / ``citations`` are the corresponding
    ORM rows in template / emit / display-index order respectively.
    """
    display_index_by_source_id = {
        c.source_id: c.display_index for c in citations if c.display_index is not None
    }

    chart_data_urls = _render_charts_to_data_urls(charts)

    rewritten_sections = []
    for section in sections:
        cleaned = strip_anthropic_citation_markup(section.markdown)
        rewritten = rewrite_section_markdown(
            section_id=section.section_id,
            title=section.title,
            markdown=cleaned,
            display_index_by_source_id=display_index_by_source_id,
        )
        rewritten_sections.append((rewritten.section_id, rewritten.title, rewritten.markdown))

    bibliography = build_bibliography(citations)

    html = _assemble(
        report=report,
        sections_in_order=rewritten_sections,
        chart_data_urls=chart_data_urls,
        charts=charts,
        bibliography=bibliography,
        now=now or datetime.now(UTC),
    )
    return AssembledReport(
        html=html,
        chart_data_urls_by_id=chart_data_urls,
        bibliography=bibliography,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_charts_to_data_urls(charts) -> dict[str, str]:
    """Render every persisted ChartSpec to a base64 ``data:`` URL.

    Falls back to an empty string for charts that fail to render. The
    chart-ref substitution treats empty strings as "[chart not
    rendered]" text so the body is never broken by one bad chart.
    """
    from ..schemas import ChartSpec  # local import — avoids cycle on package init

    out: dict[str, str] = {}
    for row in charts:
        try:
            spec = ChartSpec.model_validate_json(row.spec_json)
        except Exception:
            out[row.chart_id] = ""
            continue
        rendered: RenderedChart | None = render_chart_png(spec)
        if rendered is None or not rendered.png_bytes:
            out[row.chart_id] = ""
            continue
        b64 = base64.b64encode(rendered.png_bytes).decode("ascii")
        out[row.chart_id] = f"data:image/png;base64,{b64}"
    return out


def _substitute_chart_refs(
    html: str,
    chart_data_urls: dict[str, str],
    charts,
) -> str:
    """Replace ``{{chart:id}}`` markers in rendered HTML with figure HTML.

    Section markdown is rendered with raw-HTML passthrough disabled, so
    any HTML in the model's section text is escaped. The ``{{chart:id}}``
    markers survive that render as literal text; here they are swapped
    for trusted, fully-escaped ``<figure>`` blocks. A marker rendered on
    its own line arrives wrapped as ``<p>{{chart:id}}</p>`` — that whole
    paragraph is replaced so the figure is not nested inside a ``<p>``.
    """
    titles_by_id = {row.chart_id: row.title for row in charts}

    def _replace(match: re.Match[str]) -> str:
        standalone = match.group(1) is not None
        chart_id = match.group(1) if standalone else match.group(2)
        data_url = chart_data_urls.get(chart_id)
        title = titles_by_id.get(chart_id, chart_id)
        if not data_url:
            note = f"<em>[chart not rendered: {_escape_text(chart_id)}]</em>"
            return f"<p>{note}</p>" if standalone else note
        return (
            f'<figure class="v3-chart">'
            f'<img alt="{_escape_attr(title)}" src="{data_url}" />'
            f"<figcaption>{_escape_text(title)}</figcaption>"
            f"</figure>"
        )

    return CHART_REF_RE.sub(_replace, html)


# Static, AI-generated-report disclaimer appended to every assembled HTML/PDF
# export (no page_furniture path exists for v3/EU/MB — audit 2026-08-16 2.4).
_DISCLAIMER_HTML = (
    '<footer class="report-disclaimer" style="margin-top:2.5rem;'
    "padding-top:1rem;border-top:1px solid #d0d0d0;font-size:0.72rem;"
    'line-height:1.5;color:#666;">'
    "This report was generated by an AI system for informational purposes "
    "only. It does not constitute investment advice, a recommendation, or an "
    "offer to buy or sell any security. Verify all figures independently "
    "before making any investment decision."
    "</footer>"
)


def _assemble(
    *,
    report,
    sections_in_order,
    chart_data_urls: dict[str, str],
    charts,
    bibliography: list[BibliographyEntry],
    now: datetime,
) -> str:
    """Wrap rewritten sections in the full HTML document."""
    md_to_html = _markdown_renderer()

    section_blocks: list[str] = []
    for section_id, title, body_md in sections_in_order:
        body_html = md_to_html(body_md)
        body_html = _substitute_chart_refs(body_html, chart_data_urls, charts)
        section_blocks.append(
            f'<section class="v3-section" id="section-{_escape_attr(section_id)}">'
            f"<h2>{_escape_text(title)}</h2>"
            f"{body_html}"
            f"</section>"
        )

    bib_html = _bibliography_html(bibliography)

    cover_html = (
        f'<header class="v3-cover">'
        f"<h1>{_escape_text(report.subject)}</h1>"
        f'<p class="v3-cover-meta">'
        f"Template: {_escape_text(report.template_id)} &middot; "
        f"Language: {_escape_text(report.language)} &middot; "
        f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}"
        f"</p>"
        f"</header>"
    )

    return f"""<!DOCTYPE html>
<html lang="{_escape_attr(report.language)}">
<head>
  <meta charset="utf-8" />
  <title>{_escape_text(report.subject)} — Equity Research</title>
  <style>{_STYLES}</style>
</head>
<body>
{cover_html}
<main class="v3-body">
{"".join(section_blocks)}
</main>
{bib_html}
{_DISCLAIMER_HTML}
</body>
</html>"""


def _bibliography_html(entries: list[BibliographyEntry]) -> str:
    if not entries:
        return ""
    items: list[str] = []
    for entry in entries:
        text = _escape_text(entry.label)
        if entry.url:
            text = f'<a href="{_escape_attr(entry.url)}">{text}</a>'
        items.append(
            f'<li id="fn-{entry.display_index}">'
            f'<span class="v3-bib-index">[{entry.display_index}]</span> {text}'
            f"</li>"
        )
    return (
        '<section class="v3-bibliography">'
        "<h2>Sources</h2>"
        f'<ol class="v3-bib-list">{"".join(items)}</ol>'
        "</section>"
    )


_STYLES = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
       margin: 0; padding: 2rem 3rem; color: #111; line-height: 1.55; }
.v3-cover { border-bottom: 2px solid #111; padding-bottom: 1rem; margin-bottom: 2rem; }
.v3-cover h1 { font-size: 2rem; margin: 0 0 .25rem; }
.v3-cover-meta { color: #555; font-size: .9rem; margin: 0; }
.v3-section { margin: 2rem 0; }
.v3-section h2 { font-size: 1.4rem; border-bottom: 1px solid #ddd; padding-bottom: .25rem; }
.v3-chart { margin: 1.25rem 0; text-align: center; }
.v3-chart img { max-width: 100%; height: auto; border: 1px solid #eee; }
.v3-chart figcaption { font-size: .85rem; color: #555; margin-top: .25rem; }
.v3-bibliography { margin-top: 3rem; padding-top: 1rem; border-top: 2px solid #111; }
.v3-bib-list { list-style: none; padding-left: 0; }
.v3-bib-list li { padding: .25rem 0; font-size: .9rem; }
.v3-bib-index { font-weight: 600; margin-right: .35rem; }
code, pre { font-family: "SF Mono", Menlo, Consolas, monospace; }
"""


def _markdown_renderer():
    """Build the markdown-to-HTML callable used per section.

    Raw-HTML passthrough is disabled (``html: False``) so any HTML the
    model wrote into its section text is escaped rather than rendered
    into the ``/html`` and ``/pdf`` outputs. This matches the DOCX path
    and the browser renderer, which both neutralise raw HTML. Trusted
    chart ``<figure>`` blocks are injected afterwards, post-render, by
    ``_substitute_chart_refs``.
    """
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
    md.enable(["table"])

    def render(text: str) -> str:
        return md.render(text)

    return render


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def _escape_text(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(s: str | None) -> str:
    return _escape_text(s).replace('"', "&quot;").replace("'", "&#x27;")
