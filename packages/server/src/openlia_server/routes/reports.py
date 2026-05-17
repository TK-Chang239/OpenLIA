"""Reports API: list/read/delete, PDF export, and background generation."""

from __future__ import annotations

import html as html_escape
import json as _json
import os
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.report_export import export_report_docx, export_report_pdf
from openlia_server.services.reports import (
    ReportNotFoundError,
    get_report,
    tombstone_report,
)

_EXPIRED_DETAIL = {
    "code": "report_expired",
    "message": "This report has expired and is no longer available.",
}


def _is_tombstoned(session: DBSession, *, report_id: str, user_id: str) -> bool:
    """Return True iff the report exists, is owned by the caller, and has
    been tombstoned. Returns False on missing-or-unowned rows so the
    caller can fall through to its normal 404 path.
    """
    expired_at = session.execute(
        select(Report.expired_at).where(Report.id == report_id, Report.user_id == user_id)
    ).scalar_one_or_none()
    return expired_at is not None


def _esc(value: Any) -> str:
    return html_escape.escape(str(value))


_RATING_PALETTE: dict[str, str] = {
    "buy": "rating-buy",
    "overweight": "rating-buy",
    "outperform": "rating-buy",
    "hold": "rating-hold",
    "neutral": "rating-hold",
    "sell": "rating-sell",
    "underweight": "rating-sell",
    "underperform": "rating-sell",
}


_DELTA_DIRECTION_CLASS: dict[str, str] = {
    "up": "delta-up",
    "down": "delta-down",
    "flat": "delta-flat",
}


_FORMAT_RULE_CLASS: dict[str, str] = {
    "negative": "fmt-negative",
    "positive": "fmt-positive",
    "directional": "fmt-directional",
    "bold": "fmt-bold",
    "muted": "fmt-muted",
}


def _rating_class(rating: str) -> str:
    return _RATING_PALETTE.get(rating.strip().lower(), "rating-neutral")


def _render_metric(metric: dict, *, classes: str = "metric") -> str:
    label = _esc(metric.get("label", ""))
    value = _esc(metric.get("value", ""))
    delta = metric.get("delta")
    direction = metric.get("delta_direction") or "flat"
    parts = [
        f'<div class="{classes}">',
        f'<div class="metric-label">{label}</div>',
        f'<div class="metric-value">{value}</div>',
    ]
    if delta:
        cls = _DELTA_DIRECTION_CLASS.get(direction, "delta-flat")
        parts.append(f'<div class="metric-delta {cls}">{_esc(delta)}</div>')
    parts.append("</div>")
    return "".join(parts)


def _format_cell_value(raw: Any, *, rule: str | None) -> tuple[str, str]:
    """Return (rendered_value_str, css_class) for a table cell."""
    text = "" if raw is None else str(raw)
    if rule is None:
        return _esc(text), ""
    css = _FORMAT_RULE_CLASS.get(rule, "")
    if rule == "directional":
        try:
            n = float(text.replace(",", "").replace("%", "").replace("$", ""))
            if n < 0:
                return _esc(text), "fmt-negative"
            if n > 0:
                return _esc(text), "fmt-positive"
            return _esc(text), css
        except ValueError:
            return _esc(text), css
    return _esc(text), css


def _render_sparkline_svg(values: list[float]) -> str:
    if not values:
        return ""
    width = 80
    height = 18
    lo = min(values)
    hi = max(values)
    span = (hi - lo) or 1.0
    step = width / max(len(values) - 1, 1)
    points = " ".join(
        f"{i * step:.2f},{height - ((v - lo) / span) * height:.2f}" for i, v in enumerate(values)
    )
    return (
        f'<svg class="sparkline" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="#2563eb" stroke-width="1.2" '
        f'points="{points}" />'
        "</svg>"
    )


def _render_chart_block(block: dict) -> str:
    """Static SVG/HTML rendering of a chart block for the PDF fallback path.

    Renders the title, a tiny SVG visual where straightforward (line/bar/pie),
    and a text fallback otherwise. Real Phase 13 PDF path uses Playwright +
    React, but this fallback keeps `_schema_to_html` callable on its own and
    keeps chart titles visible in PDF when the React path is unavailable.
    """
    btype = block.get("type", "")
    title = _esc(block.get("title", btype.replace("_", " ").title()))
    parts = [f'<div class="chart chart-{_esc(btype)}">']
    parts.append(f'<div class="chart-title">{title}</div>')
    if btype in {"line_chart", "area_chart"}:
        series = block.get("series") or []
        first = next(iter(series), None)
        if first and isinstance(first, dict):
            data = first.get("data") or []
            values = [float(p.get("y", 0)) for p in data if isinstance(p, dict)]
            parts.append(_render_sparkline_svg(values))
    elif btype == "bar_chart":
        cats = block.get("categories") or []
        parts.append(f'<div class="chart-meta">{len(cats)} categories</div>')
    elif btype == "pie_chart":
        segs = block.get("segments") or []
        parts.append(
            "<ul class='pie-legend'>"
            + "".join(
                f"<li>{_esc(s.get('label', ''))}: {_esc(s.get('value', ''))}</li>" for s in segs
            )
            + "</ul>"
        )
    parts.append("</div>")
    return "".join(parts)


def _render_block(block: dict) -> str:
    btype = block.get("type", "")
    if btype == "text":
        return f"<p>{_esc(block.get('content', ''))}</p>"
    if btype == "key_finding":
        return f'<div class="key-finding"><p>{_esc(block.get("content", ""))}</p></div>'
    if btype == "rating_badge":
        rating = str(block.get("rating", "")).strip()
        prev = block.get("previous_rating")
        change = block.get("change_date")
        cls = _rating_class(rating)
        extra: list[str] = []
        if prev:
            extra.append(f"prev: {_esc(prev)}")
        if change:
            extra.append(_esc(change))
        suffix = f" <span class='rating-meta'>({' • '.join(extra)})</span>" if extra else ""
        return f'<span class="rating-badge {cls}">{_esc(rating)}</span>{suffix}'
    if btype == "metric_cards":
        metrics = block.get("metrics", []) or []
        parts = ['<div class="metrics">']
        for m in metrics:
            parts.append(_render_metric(m))
        parts.append("</div>")
        return "".join(parts)
    if btype == "table":
        title = block.get("title", "")
        headers = block.get("headers", []) or []
        rows = block.get("rows", []) or []
        cell_format = block.get("cell_format", {}) or {}
        footnotes = block.get("footnotes", []) or []
        thead_cells: list[str] = []
        for h in headers:
            align = h.get("align", "left")
            label = _esc(h.get("label", ""))
            thead_cells.append(f'<th class="text-{_esc(align)}">{label}</th>')
        body_rows: list[str] = []
        for row in rows:
            row_style = row.get("_row_style") or "default"
            row_cls = f"row-{_esc(row_style)}" if row_style != "default" else ""
            cells: list[str] = []
            for h in headers:
                key = h.get("key", "")
                rule_obj = cell_format.get(key)
                rule = rule_obj.get("rule") if isinstance(rule_obj, dict) else None
                if h.get("sparkline"):
                    raw = row.get(key) or []
                    vals: list[float] = []
                    if isinstance(raw, list):
                        for v in raw:
                            try:
                                vals.append(float(v))
                            except (TypeError, ValueError):
                                pass
                    cells.append(
                        f'<td class="text-{_esc(h.get("align", "left"))}">'
                        f"{_render_sparkline_svg(vals)}</td>"
                    )
                    continue
                rendered, css = _format_cell_value(row.get(key), rule=rule)
                align_cls = f"text-{_esc(h.get('align', 'left'))}"
                final_cls = f"{align_cls} {css}".strip()
                cells.append(f'<td class="{final_cls}">{rendered}</td>')
            body_rows.append(
                f'<tr class="{row_cls}">{"".join(cells)}</tr>'
                if row_cls
                else f"<tr>{''.join(cells)}</tr>"
            )
        parts: list[str] = []
        if title:
            parts.append(f'<div class="table-title">{_esc(title)}</div>')
        parts.append(
            "<table>"
            f"<thead><tr>{''.join(thead_cells)}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table>"
        )
        if footnotes:
            parts.append(
                "<ul class='table-footnotes'>"
                + "".join(f"<li>{_esc(fn)}</li>" for fn in footnotes)
                + "</ul>"
            )
        return "".join(parts)
    if btype == "group":
        cols = int(block.get("columns", 1) or 1)
        inner = "".join(_render_block(b) for b in block.get("blocks", []) or [])
        return (
            f'<div class="group group-cols-{cols}" '
            f'style="display:grid;grid-template-columns:repeat({cols},minmax(0,1fr));gap:12px">'
            f"{inner}</div>"
        )
    if btype.endswith("_chart") or btype in {"heatmap", "treemap", "scatter_plot"}:
        return _render_chart_block(block)
    title = block.get("title") or btype.replace("_", " ").title()
    return f'<p class="placeholder"><em>[{_esc(title)}]</em></p>'


def _render_cover(cover: dict) -> str:
    parts = [f"<h1>{_esc(cover.get('title', 'Report'))}</h1>"]
    if cover.get("subtitle"):
        parts.append(f"<p class='subtitle'><em>{_esc(cover['subtitle'])}</em></p>")
    if cover.get("ticker"):
        parts.append(f"<p class='ticker'>{_esc(cover['ticker'])}</p>")
    if cover.get("tagline"):
        parts.append(f"<p class='tagline'>{_esc(cover['tagline'])}</p>")
    key_metrics = cover.get("key_metrics") or []
    if key_metrics:
        parts.append('<div class="cover-key-metrics metrics">')
        for m in key_metrics:
            parts.append(_render_metric(m, classes="metric"))
        parts.append("</div>")
    return "".join(parts)


def _render_rail(rail: dict) -> str:
    if not rail:
        return ""
    parts: list[str] = ['<aside class="rail">']
    verdict = rail.get("verdict")
    if isinstance(verdict, dict):
        parts.append('<div class="rail-verdict">')
        if verdict.get("rating"):
            parts.append(f"<span class='rail-rating'>{_esc(verdict['rating'])}</span>")
        if verdict.get("target"):
            parts.append(f"<span class='rail-target'>{_esc(verdict['target'])}</span>")
        if verdict.get("upside"):
            parts.append(f"<span class='rail-upside'>{_esc(verdict['upside'])}</span>")
        parts.append("</div>")
    quick_stats = rail.get("quick_stats") or []
    if quick_stats:
        parts.append('<div class="rail-quick-stats">')
        for m in quick_stats:
            parts.append(
                "<div class='stat-row'>"
                f"<span class='stat-label'>{_esc(m.get('label', ''))}</span>"
                f"<span class='stat-value'>{_esc(m.get('value', ''))}</span>"
                "</div>"
            )
        parts.append("</div>")
    parts.append("</aside>")
    return "".join(parts)


def _schema_to_html(schema: dict) -> str:
    cover = schema.get("cover", {}) or {}
    parts: list[str] = [_render_cover(cover)]
    rail = schema.get("rail")
    if isinstance(rail, dict):
        parts.append(_render_rail(rail))
    for section in schema.get("sections", []) or []:
        sid = section.get("id", "")
        anchor = f' id="{_esc(sid)}"' if sid else ""
        parts.append(f"<section{anchor}><h2>{_esc(section.get('title', ''))}</h2>")
        for block in section.get("blocks", []) or []:
            parts.append(_render_block(block))
        parts.append("</section>")
    furniture = schema.get("page_furniture") or {}
    disclaimer = furniture.get("disclaimer") if isinstance(furniture, dict) else None
    if disclaimer:
        parts.append(f"<p class='disclaimer'>{_esc(disclaimer)}</p>")
    return "".join(parts)


def _furniture_template(side_dict: dict[str, str] | None, *, kind: str) -> str | None:
    """Build a minimal Playwright header/footer HTML template from
    `page_furniture.header` / `page_furniture.footer` (left/center/right keys).

    Returns None when no zones are populated. Playwright requires inline
    styles; the template uses a flex row that fills the printable width.
    """
    if not side_dict:
        return None
    left = _esc(side_dict.get("left", ""))
    center = _esc(side_dict.get("center", ""))
    right = _esc(side_dict.get("right", ""))
    if not (left or center or right):
        return None
    return (
        f'<div style="font-size:9px;width:100%;padding:0 12mm;'
        f'display:flex;justify-content:space-between;color:#555" '
        f'data-furniture-kind="{kind}">'
        f'<span class="furniture-left">{left}</span>'
        f'<span class="furniture-center">{center}</span>'
        f'<span class="furniture-right">{right}</span>'
        "</div>"
    )


def _resolve_frontend_dist() -> str | None:
    """Return abs path of frontend/dist if a built bundle is present.

    Mirrors `_mount_frontend` resolution order (env var → docker → repo).
    Returns None when no bundle exists (dev/test contexts).
    """
    candidates: list[str] = []
    dist_env = os.environ.get("OPENLIA_FRONTEND_DIST")
    if dist_env:
        candidates.append(dist_env)
    else:
        candidates.append("/app/frontend/dist")
        here = os.path.dirname(os.path.abspath(__file__))
        repo_dist = os.path.normpath(
            os.path.join(here, "..", "..", "..", "..", "..", "frontend", "dist")
        )
        candidates.append(repo_dist)
    for c in candidates:
        d = os.path.abspath(c)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "index.html")):
            return d
    return None


_BUNDLE_SCRIPT_RE = re.compile(
    r'<script[^>]*type="module"[^>]*src="([^"]+)"[^>]*>\s*</script>',
    re.IGNORECASE,
)
_BUNDLE_CSS_RE = re.compile(
    r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"[^>]*>',
    re.IGNORECASE,
)


def _spa_render_shell(report_id: str, schema: dict, dist_dir: str) -> str | None:
    """Build a minimal HTML doc that mounts the React SPA at
    `/reports/:id/render` with `window.__REPORT_SCHEMA__` pre-injected.

    Reads the Vite-built `index.html` to discover the hashed bundle path,
    then emits a tiny shell that loads the same JS/CSS and triggers SPA
    routing via `<base>` + history state. Returns None on parse failure
    so the caller can fall back to the static HTML renderer.
    """
    index_path = os.path.join(dist_dir, "index.html")
    try:
        with open(index_path, encoding="utf-8") as f:
            index_html = f.read()
    except OSError:
        return None
    script_match = _BUNDLE_SCRIPT_RE.search(index_html)
    if not script_match:
        return None
    bundle_js = script_match.group(1)
    css_match = _BUNDLE_CSS_RE.search(index_html)
    bundle_css = css_match.group(1) if css_match else None

    schema_json = _json.dumps(schema).replace("</", "<\\/")
    css_link = (
        f'<link rel="stylesheet" href="{html_escape.escape(bundle_css)}">' if bundle_css else ""
    )
    return (
        '<!doctype html><html lang="en"><head>'
        "<meta charset='utf-8'>"
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f"<title>{_esc(schema.get('cover', {}).get('title', 'Report'))}</title>"
        f"{css_link}"
        f"<script>window.__REPORT_SCHEMA__ = {schema_json};"
        f"window.__REPORT_ID__ = {_json.dumps(report_id)};</script>"
        f'<script type="module" crossorigin src="{html_escape.escape(bundle_js)}"></script>'
        '</head><body><div id="root"></div></body></html>'
    )


def _html_shell(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head>"
        "<meta charset='utf-8'>"
        f"<title>{_esc(title)}</title>"
        "<style>"
        "body{font:14px/1.5 Inter,system-ui;margin:0;padding:48px;color:#1a1a1a}"
        "h1{font-size:28px;font-weight:700;margin:0 0 8px}"
        "h2{font-size:22px;font-weight:600;margin:32px 0 12px}"
        "p{margin:0 0 12px}"
        ".subtitle{color:#555}.tagline{color:#777;margin-bottom:16px}"
        ".ticker{font-weight:600;color:#2563eb;margin-bottom:8px}"
        ".cover-key-metrics{margin:16px 0}"
        ".cover-stats-panel{border:1px solid #e5e7eb;border-radius:6px;"
        "padding:8px 12px;margin:12px 0;display:grid;"
        "grid-template-columns:1fr 1fr;gap:6px 16px}"
        ".stat-row{display:flex;justify-content:space-between}"
        ".stat-label{color:#555;font-size:12px}"
        ".stat-value{font-weight:600;font-size:13px}"
        ".key-finding{border-left:3px solid #2563eb;padding:8px 12px;"
        "margin:12px 0;background:#f8fafc}"
        ".rating-badge{display:inline-block;padding:2px 10px;border-radius:999px;"
        "font-weight:600;font-size:12px}"
        ".rating-buy{background:#dcfce7;color:#166534}"
        ".rating-hold{background:#fef9c3;color:#854d0e}"
        ".rating-sell{background:#fee2e2;color:#991b1b}"
        ".rating-neutral{background:#e5e7eb;color:#374151}"
        ".rating-meta{color:#555;font-size:11px;font-weight:400}"
        ".metrics{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}"
        ".metric{flex:1 1 160px;padding:8px 12px;border:1px solid #e5e7eb;border-radius:6px}"
        ".metric-label{color:#555;font-size:12px}"
        ".metric-value{font-size:18px;font-weight:600}"
        ".metric-delta{font-size:11px;font-weight:600}"
        ".delta-up{color:#16a34a}.delta-down{color:#dc2626}.delta-flat{color:#777}"
        ".table-title{font-weight:600;margin:16px 0 4px}"
        "table{border-collapse:collapse;width:100%;margin:8px 0}"
        "th,td{border:1px solid #e5e7eb;padding:6px 8px}"
        "th{background:#f3f4f6}"
        ".text-left{text-align:left}.text-center{text-align:center}.text-right{text-align:right}"
        ".row-subtotal{background:#f9fafb;font-weight:600}"
        ".row-total{background:#f3f4f6;font-weight:700}"
        ".row-header_group{background:#eef2ff;font-weight:600}"
        ".fmt-positive{color:#16a34a}.fmt-negative{color:#dc2626}"
        ".fmt-bold{font-weight:700}.fmt-muted{color:#6b7280}"
        ".fmt-directional{}"
        ".table-footnotes{margin:4px 0 12px;color:#6b7280;font-size:11px}"
        ".chart{margin:12px 0;padding:8px 12px;border:1px solid #e5e7eb;border-radius:6px}"
        ".chart-title{font-weight:600;margin-bottom:6px}"
        ".chart-meta{color:#6b7280;font-size:11px}"
        ".sparkline{display:inline-block}"
        ".disclaimer{color:#6b7280;font-size:11px;margin-top:24px;"
        "border-top:1px solid #e5e7eb;padding-top:8px}"
        ".placeholder{color:#777;font-style:italic}"
        "</style>"
        "</head><body>" + body + "</body></html>"
    )


class ReportListItem(BaseModel):
    id: str
    department: str
    report_type: str
    title: str
    created_at: str
    source_session_id: str | None = None
    expired_at: str | None = None


class ReportListOut(BaseModel):
    items: list[ReportListItem]


class GenerateReportIn(BaseModel):
    department_id: str
    mode: str
    user_input: str
    enabled_sections: list[str] = []
    length: str = "standard"


def _bg_enabled() -> bool:
    return os.environ.get("OPENLIA_BACKGROUND_REPORTS_ENABLED", "0") == "1"


def build_reports_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/reports", tags=["reports"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=ReportListOut)
    async def list_reports(
        department: str | None = None,
        session_id: str | None = None,
        include_expired: bool = Query(False),
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> ReportListOut:
        stmt = select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())
        if department is not None:
            stmt = stmt.where(Report.department == department)
        if session_id is not None:
            stmt = stmt.where(Report.source_session_id == session_id)
        if not include_expired:
            stmt = stmt.where(Report.expired_at.is_(None))
        rows = list(session.execute(stmt).scalars())
        return ReportListOut(
            items=[
                ReportListItem(
                    id=r.id,
                    department=r.department,
                    report_type=r.report_type,
                    title=r.title,
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    source_session_id=r.source_session_id,
                    expired_at=r.expired_at.isoformat() if r.expired_at else None,
                )
                for r in rows
            ]
        )

    @router.get("/{report_id}")
    async def read_report(
        report_id: str,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        row = session.execute(
            select(Report).where(Report.id == report_id, Report.user_id == user.id)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
        if row.expired_at is not None:
            # Tombstoned: body is blanked, schema validation would fail.
            # Return the metadata stub so chat-history surfaces can render
            # a "no longer available" card without a separate fetch.
            return {
                "schema": None,
                "expired_at": row.expired_at.isoformat(),
                "title": row.title,
                "department": row.department,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
        # Background report still generating: no schema yet, but return
        # metadata including original_request so the client can poll/retry.
        if row.status == "generating":
            return {
                "schema": None,
                "expired_at": None,
                "status": row.status,
                "original_request": row.original_request,
            }
        try:
            schema = get_report(session, report_id=report_id, user_id=user.id)
        except ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
        return {"schema": schema.model_dump(mode="json"), "expired_at": None}

    @router.post("/generate")
    async def generate_report_bg(
        body: GenerateReportIn,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> dict:
        """Submit a background report generation task.

        When OPENLIA_BACKGROUND_REPORTS_ENABLED=1, inserts a 'generating'
        row immediately and returns {report_id, status}. The real generation
        runs asynchronously; the client polls GET /reports/{id}.
        """
        if not _bg_enabled():
            raise HTTPException(
                status.HTTP_501_NOT_IMPLEMENTED,
                "background report generation is not enabled",
            )
        report_id = f"r_{uuid.uuid4().hex[:12]}"
        row = Report(
            id=report_id,
            user_id=user.id,
            department=body.department_id,
            report_type=body.mode,
            title=f"{body.department_id} — {body.user_input}",
            content_markdown="",
            content_structured={},
            model_ref="",
            status="generating",
            original_request=body.model_dump(),
            started_at=datetime.now(UTC),
        )
        session.add(row)
        session.commit()
        return {"report_id": report_id, "status": "generating"}

    @router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_report(
        report_id: str,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> None:
        # Ownership check first — 404 hides existence from non-owners.
        row = session.execute(
            select(Report).where(Report.id == report_id, Report.user_id == user.id)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
        # tombstone_report is idempotent: re-deleting an already-tombstoned
        # report is a no-op (returns False) but still 204s.
        tombstone_report(session, report_id=report_id)
        session.commit()

    @router.get("/{report_id}/render", response_class=HTMLResponse)
    async def render_report_html(
        report_id: str,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> HTMLResponse:
        """Print-friendly render of a report.

        Two output modes:
          1. SPA mode (preferred): when `frontend/dist/` exists, returns a
             minimal HTML shell that loads the Vite-built bundle with
             `window.__REPORT_SCHEMA__` pre-injected. The SPA mounts
             `<ReportRenderer>` at `/reports/:id/render` so ECharts renders
             vector graphics and the print stylesheet drives pagination.
          2. Static fallback: when no bundle is available (dev/test), returns
             a self-contained HTML document with chart titles, metric cards,
             tables, and disclaimer baked in. Used by Playwright for PDF
             export when the bundle path isn't reachable.
        """
        if _is_tombstoned(session, report_id=report_id, user_id=user.id):
            raise HTTPException(status.HTTP_410_GONE, detail=_EXPIRED_DETAIL)
        try:
            schema = get_report(session, report_id=report_id, user_id=user.id)
        except ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
        payload = schema.model_dump(mode="json")
        dist_dir = _resolve_frontend_dist()
        if dist_dir is not None:
            spa_html = _spa_render_shell(report_id, payload, dist_dir)
            if spa_html is not None:
                return HTMLResponse(spa_html)
        body = _schema_to_html(payload)
        return HTMLResponse(
            _html_shell(
                title=payload.get("cover", {}).get("title", "Report"),
                body=body,
            )
        )

    @router.api_route("/{report_id}/export/pdf", methods=["GET", "POST"])
    async def export_report_pdf_route(
        report_id: str,
        request: Request,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> Response:
        if _is_tombstoned(session, report_id=report_id, user_id=user.id):
            raise HTTPException(status.HTTP_410_GONE, detail=_EXPIRED_DETAIL)
        try:
            schema = get_report(session, report_id=report_id, user_id=user.id)
        except ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
        launcher = getattr(request.app.state, "browser_launcher", None)
        if launcher is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "PDF export unavailable (browser launcher not configured)",
            )
        payload = schema.model_dump(mode="json")
        html = _html_shell(
            title=payload.get("cover", {}).get("title", "Report"),
            body=_schema_to_html(payload),
        )
        furniture = payload.get("page_furniture") or {}
        header_html = _furniture_template(furniture.get("header"), kind="header")
        footer_html = _furniture_template(furniture.get("footer"), kind="footer")
        # SPA-driven PDF flow (Option A). Opt-in via env var because it
        # requires a live HTTP server reachable from Playwright and a
        # built `frontend/dist/`. When unset, the static-fallback HTML
        # path runs (still ships chart titles for the byte-count gate).
        bundle_base = os.environ.get("OPENLIA_REPORT_RENDER_BASE_URL")
        bundle_url: str | None = None
        cookies: list[dict[str, Any]] | None = None
        if bundle_base and _resolve_frontend_dist() is not None:
            bundle_url = f"{bundle_base.rstrip('/')}/reports/{report_id}/render"
            # Forward the request's session cookie so the SPA can fetch
            # /api/reports/:id against the protected backend. Falls back
            # to set_content if no cookie is present.
            session_cookie = request.cookies.get("openlia_session") or request.cookies.get(
                "session"
            )
            if session_cookie:
                from urllib.parse import urlparse

                parsed = urlparse(bundle_base)
                cookies = [
                    {
                        "name": "openlia_session",
                        "value": session_cookie,
                        "domain": parsed.hostname or "127.0.0.1",
                        "path": "/",
                    }
                ]
        pdf = await export_report_pdf(
            launcher,
            html,
            header_html=header_html,
            footer_html=footer_html,
            bundle_url=bundle_url,
            cookies=cookies,
        )
        filename = f"report-{report_id}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"content-disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/{report_id}/docx")
    async def export_report_docx_route(
        report_id: str,
        user: User = require_auth,
        session: DBSession = Depends(session_dep),
    ) -> Response:
        if _is_tombstoned(session, report_id=report_id, user_id=user.id):
            raise HTTPException(status.HTTP_410_GONE, detail=_EXPIRED_DETAIL)
        try:
            schema = get_report(session, report_id=report_id, user_id=user.id)
        except ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
        payload = schema.model_dump(mode="json")
        data = export_report_docx(payload)
        filename = f"report-{report_id}.docx"
        return Response(
            content=data,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            headers={"content-disposition": f'attachment; filename="{filename}"'},
        )

    return router
