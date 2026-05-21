from __future__ import annotations

import html

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark")


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_block(b: dict) -> str:
    t = b.get("type")

    if t == "prose":
        return f'<div class="prose">{_md.render(b.get("text", ""))}</div>'

    if t == "table":
        headers = "".join(f"<th>{_esc(h)}</th>" for h in b.get("headers", []))
        rows = "".join(
            "<tr>" + "".join(f"<td>{_esc(str(c))}</td>" for c in r) + "</tr>"
            for r in b.get("rows", [])
        )
        caption = f"<caption>{_esc(b['caption'])}</caption>" if b.get("caption") else ""
        return (
            f'<table class="report-table">'
            f"{caption}"
            f"<thead><tr>{headers}</tr></thead>"
            f"<tbody>{rows}</tbody>"
            f"</table>"
        )

    if t == "kpi_strip":
        cells = "".join(
            f'<div class="kpi-cell">'
            f'<div class="kpi-label">{_esc(c["label"])}</div>'
            f'<div class="kpi-value">{_esc(c["value"])}</div>'
            + (f'<div class="kpi-delta">{_esc(c["delta"])}</div>' if c.get("delta") else "")
            + "</div>"
            for c in b.get("cells", [])
        )
        return f'<div class="kpi-strip">{cells}</div>'

    if t == "chart":
        if b.get("format") == "svg_inline":
            inner = b.get("payload", "")
        else:
            inner = f'<img src="data:image/png;base64,{_esc(b.get("payload", ""))}" alt="chart">'
        cap = f"<figcaption>{_esc(b['caption'])}</figcaption>" if b.get("caption") else ""
        return f'<figure class="report-chart">{inner}{cap}</figure>'

    if t == "quote_block":
        cite = f" [c:{b['citation_id']}]" if b.get("citation_id") else ""
        return (
            f'<blockquote class="source-quote">'
            f"{_esc(b['quote'])}"
            f"<footer>— {_esc(b['source'])}{cite}</footer>"
            f"</blockquote>"
        )

    if t == "skip_banner":
        return (
            f'<blockquote class="skip-banner">'
            f"<strong>{_esc(b['section_name'])}</strong> — skipped"
            f"<br/>{_esc(b['reason'])}"
            f"</blockquote>"
        )

    if t == "degraded_banner":
        issues = ", ".join(_esc(i) for i in b.get("issue_list", []))
        return (
            f'<blockquote class="degraded-banner">'
            f"<strong>{_esc(b['section_name'])}</strong> — degraded"
            f"<br/>{_esc(b['reason'])}"
            f"<br/><small>Issues: {issues}</small>"
            f"</blockquote>"
        )

    if t == "excel_attachment":
        return (
            f'<a class="attachment" download href="{_esc(b["download_url"])}">'
            f"{_esc(b['filename'])}"
            f" ({b['row_count']} rows, {b['sheet_count']} sheets)"
            f"</a>"
        )

    raise ValueError(f"unknown block type: {t!r}")
