from __future__ import annotations

import html

from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary

_STATUS_CLASS = {
    "OK": "ok",
    "SKIPPED": "skipped",
    "DEGRADED": "degraded",
    "FAILED": "failed",
}


def render_run_summary(rs: RunSummary) -> str:
    parts: list[str] = []

    parts.append('<section id="run_summary"><h2>Run Summary</h2>')

    token_part = f" · ~{rs.total_token_cost} tokens" if rs.total_token_cost is not None else ""
    parts.append(
        f"<p><strong>Engine v{html.escape(rs.engine_version)}</strong>"
        f" · Template: {html.escape(rs.template_name)}"
        f" · {rs.total_duration_ms} ms{token_part}</p>"
    )

    if rs.composer_inputs:
        items = ", ".join(
            f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in rs.composer_inputs.items()
        )
        parts.append(f"<p>Composer inputs: {items}</p>")

    parts.append("<h3>Task outcomes</h3>")
    parts.append('<table class="run-summary-outcomes">')
    parts.append("<thead><tr><th>Type</th><th>Task</th><th>Status</th><th>Notes</th></tr></thead>")
    parts.append("<tbody>")
    for outcome in rs.outcomes:
        css = _STATUS_CLASS[outcome.status]
        notes = html.escape(outcome.notes) if outcome.notes else ""
        parts.append(
            f'<tr class="status-{css}">'
            f"<td>{html.escape(outcome.task_type)}</td>"
            f"<td>{html.escape(outcome.task_name)}</td>"
            f"<td>{html.escape(outcome.status)}</td>"
            f"<td>{notes}</td>"
            f"</tr>"
        )
    parts.append("</tbody></table>")

    parts.append("<h3>Requests not fulfilled</h3>")

    parts.append("<p>Acknowledged (dismissed at start):</p>")
    if rs.unsupported_requests_dismissed:
        items_html = "".join(
            f"<li>{html.escape(item)}</li>" for item in rs.unsupported_requests_dismissed
        )
        parts.append(f"<ul>{items_html}</ul>")
    else:
        parts.append("<p>(none)</p>")

    parts.append("<p>Detected at runtime:</p>")
    if rs.unsupported_requests_slipped:
        items_html = "".join(
            f"<li>{html.escape(item)}</li>" for item in rs.unsupported_requests_slipped
        )
        parts.append(f"<ul>{items_html}</ul>")
    else:
        parts.append("<p>(none)</p>")

    cache_entries = [
        (src, stats)
        for src, stats in rs.cache_stats.items()
        if isinstance(stats, dict) and "hits" in stats and "misses" in stats
    ]
    if cache_entries:
        parts.append("<h3>Cache</h3><ul>")
        for src, stats in cache_entries:
            parts.append(
                f"<li>{html.escape(str(src))}: {stats['hits']} hit / {stats['misses']} miss</li>"
            )
        parts.append("</ul>")

    parts.append("</section>")
    return "\n".join(parts)
