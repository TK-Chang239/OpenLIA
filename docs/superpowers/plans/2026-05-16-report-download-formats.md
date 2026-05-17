# Report Download Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace today's broken/cheap report downloads with high-fidelity **PDF** and **Word (.docx)** exports that match the in-browser view, served from a single shared download button on every surface that lists or opens reports. Drop Markdown.

**Architecture:**
The PDF path becomes SPA-driven only — Playwright navigates to the existing React print page (`/reports/:id/render`), waits for `window.__REPORT_READY__`, and captures the rendered DOM as PDF. The static-HTML fallback is removed. The DOCX path uses the same Playwright render: it screenshots each chart block by stable selector, then walks the schema in Python to emit a Word-native document (hybrid layout) with chart PNGs inlined and tables/text/metric-cards as native Word elements. The render base URL auto-detects between built `frontend/dist` (prod) and a Vite dev server on `:5173` (dev). A single `<ReportDownloadButton>` component is dropped into every report-listing/viewing surface; markdown download paths are deleted.

**Tech Stack:**
- Backend: FastAPI, Playwright (Chromium), python-docx, Pillow (for image sizing math), pydantic v2
- Frontend: React + TypeScript, Vite, vitest
- Tests: pytest + httpx (backend), vitest + Testing Library (frontend)

**Branch:** `feat/report-download-formats` (already checked out)

---

## Pre-flight: shared conventions

Before any task, the engineer should know:

- **Project root:** `/Users/tkchang/Projects/OpenLIA`
- **Always use `uv` for Python** (`uv run pytest`, `uv add <pkg>`). The Claude Code sandbox blocks uv cache writes — when running Bash via the harness, set `dangerouslyDisableSandbox: true` for any `uv run …` or `gh …` command.
- **Lint:** `uv run ruff check . && uv run ruff format .`
- **Frontend tests:** `cd frontend && npm run test -- <pattern>`
- **Frontend typecheck:** `cd frontend && npm run typecheck`
- **No emojis anywhere.** Modern strict Python type hints. Fail loud.
- **Commit per step** with conventional-commit subjects (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`). Each commit should leave the repo green (tests + lint).
- **Filename helper used everywhere:** `derive_report_title(mode, schema)` already exists in `packages/server/src/openlia_server/services/reports.py`. We will reuse it for the `content-disposition` filename.

---

## Phase 1 — PDF Quality Fix

**Why first:** the highest-leverage change. Today's PDF falls back to a hand-rolled HTML stringifier that produces "cheap-looking" output without vector charts. Flipping the SPA-driven path on by default and removing the fallback makes the next PDF the user downloads look identical to the browser view.

**Files involved:**
- Modify: `packages/server/src/openlia_server/services/report_export.py`
- Modify: `packages/server/src/openlia_server/routes/reports.py:589-654`
- Create: `packages/server/src/openlia_server/services/render_base_url.py`
- Test: `packages/server/tests/services/test_render_base_url.py`
- Test: `packages/server/tests/routes/test_reports_pdf.py` (extend)
- Modify: `packages/server/src/openlia_server/app.py` (wire startup hook for base URL resolution)

### Task 1.1 — Render base-URL resolver service

Create a small service that picks the URL Playwright should navigate to.

**Resolution order:**
1. Explicit `OPENLIA_REPORT_RENDER_BASE_URL` env var.
2. If `frontend/dist/index.html` exists in the repo root → server's own URL (default `http://127.0.0.1:8000`).
3. Probe `http://127.0.0.1:5173` with a 200ms HEAD — if 2xx/3xx, use it (Vite dev server).
4. Return `None` → caller raises 503 with a clear remediation message.

The resolver is **lazy** and **cacheable**: resolved once on first download, but re-evaluated if a download fails so spinning up Vite mid-session still works.

**Files:**
- Create: `packages/server/src/openlia_server/services/render_base_url.py`
- Create: `packages/server/tests/services/test_render_base_url.py`

- [ ] **Step 1: Write failing test for env-var precedence**

```python
# packages/server/tests/services/test_render_base_url.py
from __future__ import annotations

import pytest

from openlia_server.services.render_base_url import RenderBaseUrlResolver


def test_env_var_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_REPORT_RENDER_BASE_URL", "https://example.test")
    resolver = RenderBaseUrlResolver(
        repo_root="/nope",
        server_url="http://127.0.0.1:8000",
        probe=lambda url: False,
    )
    assert resolver.resolve() == "https://example.test"
```

Run: `cd /Users/tkchang/Projects/OpenLIA && uv run pytest packages/server/tests/services/test_render_base_url.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia_server.services.render_base_url'`.

- [ ] **Step 2: Create the resolver module with minimal happy path**

```python
# packages/server/src/openlia_server/services/render_base_url.py
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Final

_DEFAULT_VITE_URL: Final[str] = "http://127.0.0.1:5173"


class RenderBaseUrlResolver:
    """Resolve the URL Playwright should load to render a report print page.

    Resolution order (first match wins):
      1. OPENLIA_REPORT_RENDER_BASE_URL env var
      2. server's own URL, if `frontend/dist/index.html` exists
      3. Vite dev server at http://127.0.0.1:5173, if probe succeeds
      4. None — caller surfaces a 503 with remediation hint
    """

    def __init__(
        self,
        *,
        repo_root: str | Path,
        server_url: str,
        probe: Callable[[str], bool],
        vite_url: str = _DEFAULT_VITE_URL,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._server_url = server_url.rstrip("/")
        self._probe = probe
        self._vite_url = vite_url.rstrip("/")
        self._cached: str | None = None

    def resolve(self) -> str | None:
        if self._cached:
            return self._cached
        env = os.environ.get("OPENLIA_REPORT_RENDER_BASE_URL")
        if env:
            self._cached = env.rstrip("/")
            return self._cached
        if (self._repo_root / "frontend" / "dist" / "index.html").exists():
            self._cached = self._server_url
            return self._cached
        if self._probe(self._vite_url):
            self._cached = self._vite_url
            return self._cached
        return None

    def invalidate(self) -> None:
        self._cached = None
```

- [ ] **Step 3: Verify Step 1 test passes**

Run: `cd /Users/tkchang/Projects/OpenLIA && uv run pytest packages/server/tests/services/test_render_base_url.py::test_env_var_wins -v`
Expected: PASS.

- [ ] **Step 4: Add tests for dist precedence, Vite probe, and final-None fallback**

```python
# append to packages/server/tests/services/test_render_base_url.py
def test_falls_through_to_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("<html/>")
    resolver = RenderBaseUrlResolver(
        repo_root=tmp_path,
        server_url="http://127.0.0.1:8000",
        probe=lambda url: False,
    )
    assert resolver.resolve() == "http://127.0.0.1:8000"


def test_falls_through_to_vite_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    probes: list[str] = []

    def fake_probe(url: str) -> bool:
        probes.append(url)
        return True

    resolver = RenderBaseUrlResolver(
        repo_root=tmp_path,
        server_url="http://127.0.0.1:8000",
        probe=fake_probe,
    )
    assert resolver.resolve() == "http://127.0.0.1:5173"
    assert probes == ["http://127.0.0.1:5173"]


def test_returns_none_when_no_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    resolver = RenderBaseUrlResolver(
        repo_root=tmp_path,
        server_url="http://127.0.0.1:8000",
        probe=lambda url: False,
    )
    assert resolver.resolve() is None


def test_invalidate_re_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    calls = {"n": 0}

    def fake_probe(url: str) -> bool:
        calls["n"] += 1
        return calls["n"] >= 2

    resolver = RenderBaseUrlResolver(
        repo_root=tmp_path,
        server_url="http://127.0.0.1:8000",
        probe=fake_probe,
    )
    assert resolver.resolve() is None
    resolver.invalidate()
    assert resolver.resolve() == "http://127.0.0.1:5173"
```

Add `from pathlib import Path` to test imports.

Run: `uv run pytest packages/server/tests/services/test_render_base_url.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Add an HTTP HEAD-based default probe and a smoke test that monkeypatches it**

```python
# append to packages/server/src/openlia_server/services/render_base_url.py
import socket
from urllib.parse import urlparse


def default_probe(url: str, *, timeout_sec: float = 0.2) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False
```

The default probe uses a TCP-connect rather than HTTP to keep it self-contained and avoid pulling in `httpx` here. Add one test:

```python
def test_default_probe_returns_false_for_closed_port() -> None:
    from openlia_server.services.render_base_url import default_probe

    # Port 1 is reserved/never open on dev machines
    assert default_probe("http://127.0.0.1:1", timeout_sec=0.05) is False
```

Run: `uv run pytest packages/server/tests/services/test_render_base_url.py -v`
Expected: 5/5 PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/server/src/openlia_server/services/render_base_url.py packages/server/tests/services/test_render_base_url.py
uv run ruff format packages/server/src/openlia_server/services/render_base_url.py packages/server/tests/services/test_render_base_url.py
git add packages/server/src/openlia_server/services/render_base_url.py packages/server/tests/services/test_render_base_url.py
git commit -m "feat(reports): add render-base-URL resolver with env/dist/Vite fallback"
```

### Task 1.2 — Wire resolver into app state

Attach a singleton resolver to `app.state.render_base_url_resolver` on startup so route handlers can use it.

- [ ] **Step 1: Write failing test**

```python
# packages/server/tests/routes/test_reports_pdf.py — extend existing file or create
def test_render_base_url_resolver_attached_to_app_state(test_app) -> None:
    """The FastAPI app should expose a render-base-URL resolver via app.state."""
    assert hasattr(test_app.state, "render_base_url_resolver")
    assert test_app.state.render_base_url_resolver is not None
```

`test_app` is the existing FastAPI app fixture — check `packages/server/tests/conftest.py` for the actual fixture name and adapt.

Run: `uv run pytest packages/server/tests/routes/test_reports_pdf.py -k render_base_url -v`
Expected: FAIL.

- [ ] **Step 2: Attach resolver during app startup**

In `packages/server/src/openlia_server/app.py`, find the existing `lifespan` / startup function that creates `browser_launcher`. Add:

```python
from openlia_server.services.render_base_url import RenderBaseUrlResolver, default_probe

# inside the startup block, after creating browser_launcher
app.state.render_base_url_resolver = RenderBaseUrlResolver(
    repo_root=Path(__file__).resolve().parents[4],  # repo root
    server_url=os.environ.get("OPENLIA_SERVER_URL", "http://127.0.0.1:8000"),
    probe=default_probe,
)
```

Adjust the `parents[N]` depth so it lands on the repo root containing `frontend/`. Verify by adding a one-time `print(repr(...))` and reading the test output, then remove the print.

- [ ] **Step 3: Verify test passes; commit**

```bash
uv run pytest packages/server/tests/routes/test_reports_pdf.py -k render_base_url -v
uv run ruff check packages/server/src/openlia_server/app.py
git add packages/server/src/openlia_server/app.py packages/server/tests/routes/test_reports_pdf.py
git commit -m "feat(reports): attach render-base-URL resolver to app state on startup"
```

### Task 1.3 — Replace static-HTML fallback in PDF route

Today the route falls back to `_schema_to_html` whenever the env var is unset. Change the route to:
1. Ask the resolver for the base URL.
2. If `None` → 503 with `"Report rendering requires a built frontend (npm run build) or a running Vite dev server on :5173. Set OPENLIA_REPORT_RENDER_BASE_URL to override."`
3. Always navigate Playwright to `<base>/reports/<id>/render`.
4. Use the derived report title in `content-disposition`.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py:589-654`
- Modify: `packages/server/src/openlia_server/services/report_export.py:157-202` (remove `bundle_url`-vs-`html` branching; `bundle_url` is now required)

- [ ] **Step 1: Write failing test — PDF route returns 503 with clear message when resolver returns None**

```python
# packages/server/tests/routes/test_reports_pdf.py
def test_pdf_route_returns_503_when_no_render_base_url(authed_client, seeded_report_id):
    # arrange: monkeypatch the resolver to return None
    from openlia_server.services.render_base_url import RenderBaseUrlResolver
    app = authed_client.app
    app.state.render_base_url_resolver = type(
        "R", (), {"resolve": lambda self: None, "invalidate": lambda self: None}
    )()

    resp = authed_client.get(f"/api/reports/{seeded_report_id}/export/pdf")
    assert resp.status_code == 503
    assert "frontend" in resp.json()["detail"].lower()
```

Use the existing authed-client and seeded-report fixtures (look in `conftest.py`; if a "seeded_report_id" fixture doesn't exist, create a minimal one that inserts a Report row with a non-empty `content_structured`).

Run: `uv run pytest packages/server/tests/routes/test_reports_pdf.py -k 503 -v`
Expected: FAIL (route currently 200s or falls back).

- [ ] **Step 2: Write second failing test — PDF route uses derived title in filename**

```python
def test_pdf_filename_uses_derived_title(authed_client, seeded_report_id, monkeypatch):
    # arrange: stub export_report_pdf to return canned bytes so the route
    # never actually launches Playwright
    from openlia_server.services import report_export

    async def fake_export(*args, **kwargs):
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(report_export, "export_report_pdf", fake_export)

    # also stub the resolver
    app = authed_client.app
    app.state.render_base_url_resolver = type(
        "R", (), {"resolve": lambda self: "http://test", "invalidate": lambda self: None}
    )()

    resp = authed_client.get(f"/api/reports/{seeded_report_id}/export/pdf")
    assert resp.status_code == 200
    cd = resp.headers["content-disposition"]
    assert ".pdf" in cd
    # seeded_report should have a known title like "Acme Initiation"
    assert "Acme" in cd or "Initiation" in cd
```

Run: `uv run pytest packages/server/tests/routes/test_reports_pdf.py -k filename -v`
Expected: FAIL (current filename is `report-{id}.pdf`).

- [ ] **Step 3: Refactor `export_report_pdf` — `bundle_url` becomes required**

In `packages/server/src/openlia_server/services/report_export.py`, change the function signature:

```python
async def export_report_pdf(
    launcher: BrowserLauncher,
    *,
    bundle_url: str,
    header_html: str | None = None,
    footer_html: str | None = None,
    cookies: list[dict[str, Any]] | None = None,
) -> bytes:
    """Render a report's print page to PDF via Playwright.

    Navigates to `bundle_url` (the SPA's `/reports/:id/render` route) and
    captures the rendered DOM as PDF. The page is expected to signal
    readiness via `window.__REPORT_READY__ = true`; we wait for that
    flag in addition to `networkidle`.
    """
    browser = await launcher.browser()
    context = await browser.new_context()
    try:
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto(bundle_url, wait_until="networkidle")
        # Wait for the SPA's explicit ready flag (set by ReportPrintPage).
        await page.wait_for_function("window.__REPORT_READY__ === true", timeout=15_000)
        kwargs: dict[str, Any] = {
            "format": "A4",
            "margin": {"top": "20mm", "bottom": "25mm", "left": "20mm", "right": "20mm"},
            "print_background": True,
        }
        if header_html or footer_html:
            kwargs["display_header_footer"] = True
            if header_html:
                kwargs["header_template"] = header_html
            if footer_html:
                kwargs["footer_template"] = footer_html
        return await page.pdf(**kwargs)
    finally:
        await context.close()
```

Remove the old `html` positional parameter; the static-fallback `page.set_content` branch is gone.

- [ ] **Step 4: Rewrite the PDF route to use the resolver and derived title**

In `packages/server/src/openlia_server/routes/reports.py`, replace the body of the `export_report_pdf_route` handler (around line 589-654) with:

```python
from openlia_server.services.reports import derive_report_title
from urllib.parse import quote as urlquote


@router.get("/{report_id}/export/pdf")
async def export_report_pdf_route(
    report_id: str,
    request: Request,
    user: User = require_auth,
    session: DBSession = Depends(session_dep),
) -> Response:
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
    resolver = getattr(request.app.state, "render_base_url_resolver", None)
    base_url = resolver.resolve() if resolver else None
    if base_url is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Report rendering requires a built frontend (npm run build) or a "
            "running Vite dev server on :5173. Set "
            "OPENLIA_REPORT_RENDER_BASE_URL to override.",
        )

    payload = schema.model_dump(mode="json")
    furniture = payload.get("page_furniture") or {}
    header_html = _furniture_template(furniture.get("header"), kind="header")
    footer_html = _furniture_template(furniture.get("footer"), kind="footer")

    # Cookie forwarding so the SPA can call /api/reports/:id behind auth.
    cookies: list[dict[str, Any]] | None = None
    session_cookie = request.cookies.get("openlia_session") or request.cookies.get("session")
    if session_cookie:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        cookies = [
            {
                "name": "openlia_session",
                "value": session_cookie,
                "domain": parsed.hostname or "127.0.0.1",
                "path": "/",
            }
        ]

    bundle_url = f"{base_url}/reports/{report_id}/render"
    try:
        pdf = await export_report_pdf(
            launcher,
            bundle_url=bundle_url,
            header_html=header_html,
            footer_html=footer_html,
            cookies=cookies,
        )
    except Exception as exc:
        # If render fails, invalidate the cached base URL so a retry can
        # re-probe (handy when Vite was just started).
        if resolver:
            resolver.invalidate()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"PDF rendering failed: {exc}",
        ) from exc

    title = derive_report_title(payload.get("mode"), schema)
    filename = _sanitize_filename(f"{title}.pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "content-disposition": f'attachment; filename="{filename}"; '
            f"filename*=UTF-8''{urlquote(filename)}"
        },
    )
```

Add a `_sanitize_filename` helper in the same file (or import from a util):

```python
import re

_FILENAME_INVALID = re.compile(r'[\x00-\x1f/\\:*?"<>|]')


def _sanitize_filename(name: str) -> str:
    cleaned = _FILENAME_INVALID.sub("", name).strip().strip(".")
    return cleaned or "report"
```

Delete the now-unused `_schema_to_html`, `_html_shell`, and any helpers feeding the removed fallback path.

- [ ] **Step 5: Verify both tests pass**

Run: `uv run pytest packages/server/tests/routes/test_reports_pdf.py -v`
Expected: PASS.

- [ ] **Step 6: Run full server suite to catch regressions**

Run: `uv run pytest packages/server/tests/ -x` (this will be slow; if too noisy, scope to `packages/server/tests/routes/ packages/server/tests/services/`).
Expected: green except for the documented pre-existing migration test failures (2 known failures noted in memory).

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check . && uv run ruff format .
git add -u
git commit -m "feat(reports): SPA-driven PDF only — kill static-HTML fallback, use derived title in filename"
```

### Task 1.4 — Frontend smoke: confirm `__REPORT_READY__` flag

The PDF route's `page.wait_for_function` depends on `window.__REPORT_READY__` being set by the print page. Verify the React side already does this.

- [ ] **Step 1: Inspect `ReportPrintPage.tsx`**

Read: `frontend/src/pages/ReportPrintPage.tsx`.

Expected: there's already a `useEffect` that sets `window.__REPORT_READY__ = true` once the schema has rendered. If it doesn't, add it:

```tsx
useEffect(() => {
  if (schema && !loading) {
    // delay one frame so charts have mounted
    requestAnimationFrame(() => {
      // @ts-expect-error: writing to window for headless polling
      window.__REPORT_READY__ = true;
    });
  }
}, [schema, loading]);
```

- [ ] **Step 2: Manual smoke via dev**

In one terminal: `cd /Users/tkchang/Projects/OpenLIA && uv run openlia serve`
In another: `cd frontend && npm run dev`
In a third: `curl -o /tmp/test.pdf -b "openlia_session=<your session cookie>" http://127.0.0.1:8000/api/reports/<a-real-report-id>/export/pdf`

Open `/tmp/test.pdf`. It should match the browser print preview — vector charts, full styling. If it looks wrong, debug before continuing.

- [ ] **Step 3: Commit (if any changes were needed)**

```bash
git add frontend/src/pages/ReportPrintPage.tsx
git commit -m "fix(reports): set __REPORT_READY__ after charts mount for headless capture"
```

---

## Phase 2 — Shared `<ReportDownloadButton>` component

**Why:** every surface needs the same dropdown. Building a single shared component (with PDF + DOCX options, in-app spinner, toast on error) and then dropping it into every surface in Phase 3 keeps the UI consistent and the rollout fast.

**Files involved:**
- Create: `frontend/src/components/report/ReportDownloadButton.tsx`
- Create: `frontend/src/components/report/__tests__/ReportDownloadButton.test.tsx`
- Modify: `frontend/src/api/reports.ts` (add `downloadReportAsBlob` helper)

### Task 2.1 — Blob-download API helper

A small `fetch` wrapper that hits the export endpoint with credentials, reads the blob, and triggers a save with the server-provided filename.

- [ ] **Step 1: Write failing vitest**

```typescript
// frontend/src/api/__tests__/reports-download.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { downloadReportBlob } from "../reports";

describe("downloadReportBlob", () => {
  let originalFetch: typeof globalThis.fetch;
  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetches /api/reports/:id/export/pdf with credentials", async () => {
    const fakeFetch = vi.fn().mockResolvedValue(
      new Response(new Blob(["%PDF"]), {
        status: 200,
        headers: {
          "content-disposition": 'attachment; filename="Acme.pdf"',
        },
      }),
    );
    globalThis.fetch = fakeFetch as unknown as typeof fetch;

    const result = await downloadReportBlob("abc", "pdf");
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/reports/abc/export/pdf",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(result.filename).toBe("Acme.pdf");
    expect(result.blob.size).toBeGreaterThan(0);
  });

  it("throws DownloadError on non-2xx", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "no frontend" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    await expect(downloadReportBlob("abc", "pdf")).rejects.toThrowError(/no frontend/);
  });
});
```

Run: `cd frontend && npm run test -- src/api/__tests__/reports-download.test.ts`
Expected: FAIL (`downloadReportBlob` not exported).

- [ ] **Step 2: Add the helper to `frontend/src/api/reports.ts`**

```typescript
export type DownloadFormat = "pdf" | "docx";

export interface DownloadResult {
  blob: Blob;
  filename: string;
}

export class DownloadError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "DownloadError";
  }
}

const FILENAME_RE = /filename\*?=(?:UTF-8'')?["']?([^;"']+)["']?/i;

function parseFilename(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) return fallback;
  const m = contentDisposition.match(FILENAME_RE);
  if (!m) return fallback;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
}

export async function downloadReportBlob(
  reportId: string,
  format: DownloadFormat,
): Promise<DownloadResult> {
  const url =
    format === "pdf"
      ? `/api/reports/${reportId}/export/pdf`
      : `/api/reports/${reportId}/export/docx`;
  const resp = await fetch(url, { credentials: "include" });
  if (!resp.ok) {
    let detail = `Download failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // not JSON; keep generic message
    }
    throw new DownloadError(resp.status, detail);
  }
  const blob = await resp.blob();
  const filename = parseFilename(
    resp.headers.get("content-disposition"),
    `report-${reportId}.${format}`,
  );
  return { blob, filename };
}

export function triggerBrowserSave(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // revoke after the browser has had time to start the save
  setTimeout(() => URL.revokeObjectURL(url), 5_000);
}
```

Note: PDF endpoint is `/api/reports/:id/export/pdf` (existing). DOCX endpoint will be aligned to `/api/reports/:id/export/docx` in Task 4.1 — for now it's `/{id}/docx`. **Choose one URL and stick with it.** The plan uses `/export/docx` for symmetry; update the existing route in Task 4.1.

- [ ] **Step 3: Verify tests pass; commit**

```bash
cd frontend && npm run test -- src/api/__tests__/reports-download.test.ts
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/api/reports.ts frontend/src/api/__tests__/reports-download.test.ts
git commit -m "feat(reports): add downloadReportBlob helper with credentialed fetch + filename parse"
```

### Task 2.2 — `<ReportDownloadButton>` component

A button-with-dropdown that uses `downloadReportBlob` + `triggerBrowserSave`, shows a spinner while downloading, and surfaces errors via toast.

**Visual spec:**
- A single icon button (download icon) with a chevron — opens a small popover.
- Popover lists: "Download as PDF" and "Download as Word".
- While downloading, the button shows a small spinner and is disabled.
- On error, a toast appears with the server's error detail.
- DOCX option is **hidden** unless `import.meta.env.VITE_REPORT_DOCX_ENABLED === "true"` (the feature gate during chunks 1–3).

**Props:**
```typescript
interface ReportDownloadButtonProps {
  reportId: string;
  variant?: "icon" | "primary";  // icon = compact, primary = labeled button
  className?: string;
}
```

- [ ] **Step 1: Write failing test for PDF happy path**

```typescript
// frontend/src/components/report/__tests__/ReportDownloadButton.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReportDownloadButton } from "../ReportDownloadButton";

const downloadReportBlob = vi.fn();
const triggerBrowserSave = vi.fn();
const toastError = vi.fn();

vi.mock("../../../api/reports", () => ({
  downloadReportBlob: (...args: any[]) => downloadReportBlob(...args),
  triggerBrowserSave: (...args: any[]) => triggerBrowserSave(...args),
}));

vi.mock("../../../lib/toast", () => ({
  toast: { error: (msg: string) => toastError(msg) },
}));

describe("ReportDownloadButton", () => {
  beforeEach(() => {
    downloadReportBlob.mockReset();
    triggerBrowserSave.mockReset();
    toastError.mockReset();
  });

  it("downloads as PDF when PDF option clicked", async () => {
    downloadReportBlob.mockResolvedValue({
      blob: new Blob(["pdf"]),
      filename: "AAPL.pdf",
    });
    const user = userEvent.setup();
    render(<ReportDownloadButton reportId="abc" />);
    await user.click(screen.getByRole("button", { name: /download/i }));
    await user.click(screen.getByRole("menuitem", { name: /pdf/i }));
    expect(downloadReportBlob).toHaveBeenCalledWith("abc", "pdf");
    expect(triggerBrowserSave).toHaveBeenCalledWith(expect.any(Blob), "AAPL.pdf");
  });

  it("shows toast on error", async () => {
    downloadReportBlob.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(<ReportDownloadButton reportId="abc" />);
    await user.click(screen.getByRole("button", { name: /download/i }));
    await user.click(screen.getByRole("menuitem", { name: /pdf/i }));
    expect(toastError).toHaveBeenCalledWith(expect.stringContaining("boom"));
  });
});
```

Adjust the toast import path to match the project's actual toast module — `grep -rn "import.*toast" frontend/src` to find it.

Run: `cd frontend && npm run test -- src/components/report/__tests__/ReportDownloadButton.test.tsx`
Expected: FAIL (component does not exist).

- [ ] **Step 2: Implement the component**

```tsx
// frontend/src/components/report/ReportDownloadButton.tsx
import { useCallback, useState } from "react";
import {
  downloadReportBlob,
  triggerBrowserSave,
  type DownloadFormat,
} from "../../api/reports";
import { toast } from "../../lib/toast";  // <- adjust to project's toast module

interface ReportDownloadButtonProps {
  reportId: string;
  variant?: "icon" | "primary";
  className?: string;
}

const DOCX_ENABLED = import.meta.env.VITE_REPORT_DOCX_ENABLED === "true";

export function ReportDownloadButton({
  reportId,
  variant = "icon",
  className,
}: ReportDownloadButtonProps) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const download = useCallback(
    async (fmt: DownloadFormat) => {
      setOpen(false);
      setBusy(true);
      try {
        const { blob, filename } = await downloadReportBlob(reportId, fmt);
        triggerBrowserSave(blob, filename);
      } catch (err) {
        toast.error(`Download failed: ${(err as Error).message}`);
      } finally {
        setBusy(false);
      }
    },
    [reportId],
  );

  return (
    <div className={`report-download ${className ?? ""}`} data-busy={busy}>
      <button
        type="button"
        aria-label="Download report"
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
        className={variant === "primary" ? "btn-primary" : "btn-icon"}
      >
        {busy ? <Spinner /> : <DownloadIcon />}
        {variant === "primary" && <span>Download</span>}
        <Chevron />
      </button>
      {open && (
        <ul role="menu" className="report-download__menu">
          <li role="none">
            <button
              role="menuitem"
              type="button"
              onClick={() => download("pdf")}
            >
              Download as PDF
            </button>
          </li>
          {DOCX_ENABLED && (
            <li role="none">
              <button
                role="menuitem"
                type="button"
                onClick={() => download("docx")}
              >
                Download as Word
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function Spinner() {
  return <span className="spinner" aria-hidden />;
}
function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M8 1v9M4 7l4 4 4-4M2 13h12"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function Chevron() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
      <path d="M2 4l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
```

Reuse existing icon components if the project has them — look in `frontend/src/components/icons/` first.

CSS: add minimal styles to `.report-download` and `.report-download__menu` in `frontend/src/styles/components.css` (or wherever component CSS lives). Keep it tight; use existing design tokens.

- [ ] **Step 3: Verify tests pass; lint; commit**

```bash
cd frontend && npm run test -- src/components/report/__tests__/ReportDownloadButton.test.tsx
npm run typecheck
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/components/report/ReportDownloadButton.tsx frontend/src/components/report/__tests__/ReportDownloadButton.test.tsx frontend/src/styles/components.css
git commit -m "feat(reports): add shared ReportDownloadButton with spinner + toast"
```

---

## Phase 3 — Wire button into all surfaces

**Files involved:**
- Modify: `frontend/src/pages/Repository.tsx`
- Modify: `frontend/src/components/equity-research/ReportCard.tsx`
- Modify: `frontend/src/components/morning-briefing/MBReportCard.tsx`
- Modify: `frontend/src/components/morning-briefing/MBHeroCard.tsx`
- Modify: `frontend/src/components/viewer/FileViewer.tsx` (and/or its toolbar)
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Modify: `frontend/src/pages/departments/MorningBriefing.tsx`
- Modify: `frontend/src/pages/departments/EquityResearch.tsx` (replace `handleDownload`)

For each surface, **replace the existing download link/button with `<ReportDownloadButton reportId={…} />`** and remove the now-dead local download wiring.

### Task 3.1 — Repository row action

Currently `Repository.tsx:261` passes `downloadUrl={reportPdfUrl(row.report_id)}` to row component. Find the row component, swap the download surface to `<ReportDownloadButton>`.

- [ ] **Step 1: Locate the row component**

Run: `grep -n "downloadUrl" frontend/src/pages/Repository.tsx frontend/src/components/repository/ 2>/dev/null`
Note the file that consumes `downloadUrl`.

- [ ] **Step 2: Write a test that the Repository row renders the shared download button**

In the existing `frontend/src/pages/__tests__/Repository.test.tsx`, add:

```tsx
it("renders a ReportDownloadButton in each row", async () => {
  // arrange the existing test setup with a mocked report list
  render(<Repository />);
  // wait for rows to appear (use existing wait pattern)
  const buttons = await screen.findAllByRole("button", { name: /download/i });
  expect(buttons.length).toBeGreaterThan(0);
});
```

Run: `cd frontend && npm run test -- src/pages/__tests__/Repository.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Replace the existing download link with `<ReportDownloadButton reportId={row.report_id} variant="icon" />`**

Remove the `downloadUrl` prop and any anchor / `window.open` wiring.

- [ ] **Step 4: Verify tests pass; commit**

```bash
cd frontend && npm run test -- src/pages/__tests__/Repository.test.tsx
cd /Users/tkchang/Projects/OpenLIA
git add -u
git commit -m "feat(reports): use shared ReportDownloadButton in Repository rows"
```

### Task 3.2 — FileViewer toolbar

When a report is open in the FileViewer, the toolbar should show a download button.

- [ ] **Step 1: Locate the FileViewer toolbar component**

Run: `grep -rn "FileViewer\|toolbar\|onClose\|onSave" frontend/src/components/viewer/ | head -20`

- [ ] **Step 2: Write a failing test that the toolbar renders the button when source.kind === 'report'**

(Use the existing FileViewer test file as a template.)

- [ ] **Step 3: Add `<ReportDownloadButton reportId={source.reportId} />` to the toolbar when source.kind === 'report'**

Remove any existing markdown-link wiring that goes through `downloadUrlForReport`.

- [ ] **Step 4: Verify; commit**

```bash
git add -u
git commit -m "feat(reports): add download button to FileViewer toolbar for report sources"
```

### Task 3.3 — Equity Research ReportCard

Replace the existing PDF/DOCX dropdown in `frontend/src/components/equity-research/ReportCard.tsx:206-217` with `<ReportDownloadButton reportId={reportId} />`. Remove the local `handleDownload` and `reportPdfUrl`/`reportDocxUrl` imports if they're no longer used (still used by the EquityResearch page handler — keep there until Task 3.6).

- [ ] **Step 1: Locate the dropdown** (lines around 206-217 per exploration)
- [ ] **Step 2: Update or extend the existing ReportCard test**
- [ ] **Step 3: Replace dropdown with `<ReportDownloadButton>`**
- [ ] **Step 4: Verify; commit**

```bash
git commit -m "feat(reports): swap ReportCard dropdown for shared ReportDownloadButton"
```

### Task 3.4 — Morning Briefing cards

`MBReportCard.tsx:133` and `MBHeroCard.tsx:131` both have raw `<a href={reportPdfUrl(report.id)}>` links. Replace each with `<ReportDownloadButton reportId={report.id} />`.

- [ ] **Step 1: Update tests for MB cards (look for existing tests; add minimal ones if missing)**
- [ ] **Step 2: Replace anchors with `<ReportDownloadButton>`**
- [ ] **Step 3: Same change in `MorningBriefing.tsx:138`** (the viewer's PDF anchor)
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(reports): swap MB card and viewer download anchors for shared button"
```

### Task 3.5 — Earnings Update download

`EarningsUpdate.tsx:105` uses `downloadUrlForReport(id)` (markdown). Replace the entire download-saving code block with `<ReportDownloadButton reportId={id} />`.

- [ ] **Step 1: Find the call site (around line 105 — likely inside a "Save" or "Download" handler)**
- [ ] **Step 2: Replace handler-driven download with rendered button**
- [ ] **Step 3: Commit**

```bash
git commit -m "feat(reports): replace EarningsUpdate markdown-only download with shared button"
```

### Task 3.6 — Equity Research page (the actual page, not ReportCard)

`EquityResearch.tsx:454-457` has a local `handleDownload` that opens PDF/DOCX in a new tab. Since `ReportCard` now uses the shared button, this handler should be unused. Confirm and delete.

- [ ] **Step 1: `grep -n handleDownload frontend/src/pages/departments/EquityResearch.tsx`**

If no callers remain, delete the function and the unused `reportPdfUrl`/`reportDocxUrl` imports.

- [ ] **Step 2: Run frontend typecheck**

```bash
cd frontend && npm run typecheck
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(equity-research): drop unused handleDownload now that ReportCard owns download UI"
```

### Task 3.7 — End-to-end sanity check

- [ ] **Step 1: Run full frontend test suite**

```bash
cd frontend && npm run test
```

Expected: all green except the 2 pre-existing SettingsShellBlocker failures noted in memory.

- [ ] **Step 2: Manual smoke**

Start server + Vite, open Repository, click download → confirm PDF saves with correct filename and looks correct. Open a report in FileViewer, click download → same. Open ReportCard in equity research, click download → same.

If any surface regresses, fix before continuing.

---

## Phase 4 — DOCX rewrite (high-fidelity, chart screenshots)

**Why now:** with shared button + PDF quality fixed, the DOCX flow is the last quality gap. The feature flag has been hiding DOCX in the UI; this phase implements it properly and flips the flag.

**Files involved:**
- Modify: `frontend/src/components/report/BlockRenderer.tsx` (add `data-block-id` and `data-block-type` to wrapper for chart blocks)
- Create: `packages/server/src/openlia_server/services/report_docx.py` (new module — replaces `export_report_docx` in `report_export.py`)
- Modify: `packages/server/src/openlia_server/services/report_export.py` (remove old `export_report_docx`, add new `capture_chart_pngs` Playwright helper)
- Modify: `packages/server/src/openlia_server/routes/reports.py` (rename DOCX route to `/{id}/export/docx`, wire to new service)
- Create: `packages/server/tests/services/test_report_docx.py`

### Task 4.1 — Stable chart block selectors in the print DOM

The DOCX path screenshots each chart by stable selector. Add `data-block-id` to the wrapper of every chart block so Playwright can find them.

**Schema block IDs:** the schema's `Block` model already includes `id` on most block types (verify with `grep -n "id:" packages/core/src/openlia/reports/schema.py | head -30`). If chart blocks don't have an `id` field, **add one as `id: str | None = None`** (optional, defaults None) — and have the SPA generate a stable ID per render if missing (e.g., `section_idx-block_idx`).

Decision: **use `section_idx-block_idx` as the DOM ID**, not the schema field. Reasoning: this avoids touching the core schema, and the Python side can compute the same path. The selector becomes `[data-block-path="0-3"]`.

- [ ] **Step 1: Update `BlockRenderer` to accept and emit a `blockPath`**

Modify `BlockRenderer.tsx` to wrap chart blocks in a `<div data-block-path={blockPath} data-block-type={block.type}>...</div>`. Only wrap chart blocks (types ending in `_chart`, plus `heatmap`, `treemap`, `candlestick_chart`, `scatter_plot`, `waterfall_chart`).

```tsx
export interface BlockRendererProps {
  block: any;
  forcedHeight?: ForcedHeight;
  blockPath?: string;
}

const CHART_TYPES = new Set([
  "line_chart", "bar_chart", "area_chart", "pie_chart",
  "candlestick_chart", "waterfall_chart", "scatter_plot",
  "heatmap", "treemap", "combo_chart",
]);

export function BlockRenderer({ block, forcedHeight: _forcedHeight, blockPath }: BlockRendererProps) {
  const inner = renderInner(block);  // existing switch lifted into a helper
  if (blockPath && CHART_TYPES.has(block.type)) {
    return (
      <div data-block-path={blockPath} data-block-type={block.type}>
        {inner}
      </div>
    );
  }
  return inner;
}
```

Pass `blockPath` down from `ReportSection.tsx` / wherever sections are rendered: `<BlockRenderer block={b} blockPath={\`${sectionIdx}-${blockIdx}\`} />`.

- [ ] **Step 2: Add a test that chart blocks carry the data attribute**

Update `frontend/src/components/report/__tests__/BlockRenderer.test.tsx`:

```tsx
it("wraps chart blocks with data-block-path when path is provided", () => {
  const { container } = render(
    <BlockRenderer
      block={{ type: "pie_chart", title: "x", segments: [{ label: "a", value: 1 }] }}
      blockPath="0-2"
    />,
  );
  const wrapper = container.querySelector('[data-block-path="0-2"]');
  expect(wrapper).not.toBeNull();
  expect(wrapper?.getAttribute("data-block-type")).toBe("pie_chart");
});

it("does not wrap text blocks", () => {
  const { container } = render(
    <BlockRenderer block={{ type: "text", content: "hi" }} blockPath="0-0" />,
  );
  expect(container.querySelector("[data-block-path]")).toBeNull();
});
```

- [ ] **Step 3: Verify; commit**

```bash
cd frontend && npm run test -- src/components/report/__tests__/BlockRenderer.test.tsx
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/components/report/BlockRenderer.tsx frontend/src/components/report/__tests__/BlockRenderer.test.tsx frontend/src/components/report/ReportSection.tsx
git commit -m "feat(reports): tag chart blocks with data-block-path for headless screenshot"
```

### Task 4.2 — Playwright chart-screenshot helper

A Python helper that, given a browser launcher and a bundle URL, opens the print page and returns `{block_path: png_bytes}` for every chart.

- [ ] **Step 1: Write failing test (with mocked launcher)**

```python
# packages/server/tests/services/test_capture_chart_pngs.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_capture_chart_pngs_returns_dict_keyed_by_block_path() -> None:
    from openlia_server.services.report_export import capture_chart_pngs

    fake_locator_a = MagicMock()
    fake_locator_a.screenshot = AsyncMock(return_value=b"PNG_A")
    fake_locator_b = MagicMock()
    fake_locator_b.screenshot = AsyncMock(return_value=b"PNG_B")

    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.wait_for_function = AsyncMock()
    fake_page.evaluate = AsyncMock(return_value=["0-1", "1-3"])
    fake_page.locator = MagicMock(side_effect=[fake_locator_a, fake_locator_b])

    fake_context = MagicMock()
    fake_context.add_cookies = AsyncMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)
    fake_context.close = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)

    fake_launcher = MagicMock()
    fake_launcher.browser = AsyncMock(return_value=fake_browser)

    result = await capture_chart_pngs(
        fake_launcher, bundle_url="http://test/render", cookies=None
    )

    assert result == {"0-1": b"PNG_A", "1-3": b"PNG_B"}
    fake_page.goto.assert_awaited_once_with("http://test/render", wait_until="networkidle")
```

Run: `uv run pytest packages/server/tests/services/test_capture_chart_pngs.py -v`
Expected: FAIL (function does not exist).

- [ ] **Step 2: Implement `capture_chart_pngs` in `report_export.py`**

```python
async def capture_chart_pngs(
    launcher: BrowserLauncher,
    *,
    bundle_url: str,
    cookies: list[dict[str, Any]] | None = None,
    device_scale_factor: float = 2.0,
) -> dict[str, bytes]:
    """Render a report print page and screenshot every chart block.

    Returns a mapping of `data-block-path` → PNG bytes. Charts are captured
    at 2x device scale factor for retina-sharp embedding in Word.
    """
    browser = await launcher.browser()
    context = await browser.new_context(device_scale_factor=device_scale_factor)
    try:
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto(bundle_url, wait_until="networkidle")
        await page.wait_for_function("window.__REPORT_READY__ === true", timeout=15_000)
        paths: list[str] = await page.evaluate(
            "Array.from(document.querySelectorAll('[data-block-path]'))"
            ".map(el => el.getAttribute('data-block-path'))"
        )
        out: dict[str, bytes] = {}
        for path in paths:
            locator = page.locator(f'[data-block-path="{path}"]')
            out[path] = await locator.screenshot(type="png")
        return out
    finally:
        await context.close()
```

- [ ] **Step 3: Verify test; commit**

```bash
uv run pytest packages/server/tests/services/test_capture_chart_pngs.py -v
git add packages/server/src/openlia_server/services/report_export.py packages/server/tests/services/test_capture_chart_pngs.py
git commit -m "feat(reports): add capture_chart_pngs Playwright helper at 2x DPI"
```

### Task 4.3 — DOCX assembler (hybrid Word-native layout)

Replace the existing `export_report_docx` with a richer assembler that:
- Builds cover page with title, subtitle, ticker, tagline, key metrics in a 2-col styled table.
- Walks sections, emitting Heading 1 for section titles.
- Walks blocks, emitting:
  - `text` → paragraph (with bold/italic if markdown-ish)
  - `key_finding` → bold paragraph in a shaded callout
  - `rating_badge` → bold paragraph with rating + previous
  - `metric_cards` → 2-col table styled to match the print card aesthetic
  - `table` → native Word table with header style
  - `bullet_list` → Word bullets
  - `pull_quote` / `quote` → italic indented paragraph
  - `callout_grid` → 2x2 table
  - `timeline` → bulleted list of events with dates
  - `comparison_split` → 2-col table (left vs right)
  - `group` → recurse
  - **chart blocks → embedded PNG** (from the screenshot dict), 6.5" wide
- Adds Word native header (report title) and footer (subject + date + page X of Y).
- Inserts Word native TOC field at the start (auto-refreshable by user).

**File:** `packages/server/src/openlia_server/services/report_docx.py`

- [ ] **Step 1: Write failing test for cover + a section + a pie chart**

```python
# packages/server/tests/services/test_report_docx.py
from __future__ import annotations

import io

from docx import Document


def test_assemble_docx_includes_cover_section_and_chart_image() -> None:
    from openlia_server.services.report_docx import assemble_docx

    schema = {
        "cover": {
            "title": "Acme — Initiation",
            "subtitle": "Buy at $100",
            "ticker": "ACME",
            "tagline": "Strong moat in widgets",
            "key_metrics": [
                {"label": "Price", "value": "$95"},
                {"label": "Target", "value": "$120"},
            ],
        },
        "sections": [
            {
                "id": "thesis",
                "title": "Thesis",
                "blocks": [
                    {"type": "text", "content": "Hello world"},
                    {"type": "pie_chart", "title": "Mix", "segments": []},
                ],
            }
        ],
        "page_furniture": {"footer": {"subject": "ACME", "date": "2026-05-16"}},
    }
    chart_pngs = {"0-1": _one_px_png_bytes()}

    docx_bytes = assemble_docx(schema, chart_pngs=chart_pngs, header_text="Acme — Initiation")
    doc = Document(io.BytesIO(docx_bytes))

    # cover title is the first heading
    assert any("Acme" in p.text for p in doc.paragraphs)
    # section heading present
    assert any(p.text == "Thesis" for p in doc.paragraphs)
    # an inline image was added (one image relationship beyond the default)
    image_parts = [p for p in doc.part.related_parts.values() if "image" in p.content_type]
    assert len(image_parts) >= 1


def _one_px_png_bytes() -> bytes:
    # 1x1 transparent PNG
    return bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
    )
```

Run: `uv run pytest packages/server/tests/services/test_report_docx.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement `assemble_docx`**

```python
# packages/server/src/openlia_server/services/report_docx.py
from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor


_CHART_TYPES = {
    "line_chart", "bar_chart", "area_chart", "pie_chart",
    "candlestick_chart", "waterfall_chart", "scatter_plot",
    "heatmap", "treemap", "combo_chart",
}


def assemble_docx(
    schema: dict[str, Any],
    *,
    chart_pngs: dict[str, bytes],
    header_text: str = "",
) -> bytes:
    """Build a Word document from a report schema with chart PNGs inlined.

    Layout: hybrid Word-native — cover page first, Word native TOC field,
    one Heading 1 per section, native header/footer with page numbers.
    Charts are embedded as 6.5"-wide PNG images at their schema position.
    """
    doc = Document()
    _configure_default_styles(doc)
    _set_header_footer(doc, header_text=header_text, schema=schema)
    _add_cover(doc, schema.get("cover") or {})
    _add_toc_field(doc)

    for sec_idx, section in enumerate(schema.get("sections") or []):
        doc.add_page_break() if sec_idx > 0 else None
        doc.add_heading(str(section.get("title", "")), level=1)
        for blk_idx, block in enumerate(section.get("blocks") or []):
            _render_block(
                doc,
                block,
                path=f"{sec_idx}-{blk_idx}",
                chart_pngs=chart_pngs,
            )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _configure_default_styles(doc: Document) -> None:
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)


def _add_cover(doc: Document, cover: dict[str, Any]) -> None:
    title = str(cover.get("title", "Report"))
    h = doc.add_heading(title, level=0)
    for run in h.runs:
        run.font.size = Pt(28)
    subtitle = cover.get("subtitle")
    if subtitle:
        p = doc.add_paragraph(str(subtitle))
        p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        for run in p.runs:
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    ticker = cover.get("ticker")
    if ticker:
        p = doc.add_paragraph()
        run = p.add_run(str(ticker))
        run.bold = True
    tagline = cover.get("tagline")
    if tagline:
        doc.add_paragraph(str(tagline))
    metrics = cover.get("key_metrics") or []
    if metrics:
        tbl = doc.add_table(rows=len(metrics), cols=2)
        tbl.style = "Light Grid Accent 1"
        for i, m in enumerate(metrics):
            tbl.rows[i].cells[0].text = str(m.get("label", ""))
            value = str(m.get("value", ""))
            delta = m.get("delta")
            if delta:
                value = f"{value}  ({delta})"
            tbl.rows[i].cells[1].text = value
    doc.add_page_break()


def _add_toc_field(doc: Document) -> None:
    """Insert a Word native TOC field. User refreshes via right-click."""
    p = doc.add_paragraph()
    run = p.add_run()
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
    fldChar2 = OxmlElement("w:fldChar")
    fldChar2.set(qn("w:fldCharType"), "separate")
    fldChar3 = OxmlElement("w:t")
    fldChar3.text = "Right-click to update Table of Contents"
    fldChar4 = OxmlElement("w:fldChar")
    fldChar4.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(fldChar3)
    run._r.append(fldChar4)
    doc.add_page_break()


def _set_header_footer(
    doc: Document, *, header_text: str, schema: dict[str, Any]
) -> None:
    section = doc.sections[0]
    section.header.paragraphs[0].text = header_text
    footer_p = section.footer.paragraphs[0]
    furniture = (schema.get("page_furniture") or {}).get("footer") or {}
    subject = str(furniture.get("subject") or "")
    date = str(furniture.get("date") or "")
    left = " · ".join([s for s in [subject, date] if s])
    footer_p.text = left
    # add page number field on the right
    tab_run = footer_p.add_run("\t\tPage ")
    _add_page_num_field(tab_run)
    footer_p.add_run(" of ")
    _add_pages_field(footer_p.add_run())


def _add_page_num_field(run) -> None:
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._r.append(fld)


def _add_pages_field(run) -> None:
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "NUMPAGES")
    run._r.append(fld)


def _render_block(
    doc: Document,
    block: dict[str, Any],
    *,
    path: str,
    chart_pngs: dict[str, bytes],
) -> None:
    btype = str(block.get("type", ""))
    if btype in _CHART_TYPES:
        png = chart_pngs.get(path)
        title = block.get("title")
        if title:
            p = doc.add_paragraph()
            run = p.add_run(str(title))
            run.bold = True
        if png:
            doc.add_picture(io.BytesIO(png), width=Inches(6.5))
        else:
            p = doc.add_paragraph()
            run = p.add_run(f"[chart: {title or btype}]")
            run.italic = True
        return
    if btype == "text":
        doc.add_paragraph(str(block.get("content", "")))
        return
    if btype == "key_finding":
        p = doc.add_paragraph()
        run = p.add_run(str(block.get("content", "")))
        run.bold = True
        return
    if btype == "rating_badge":
        rating = str(block.get("rating", ""))
        prev = block.get("previous_rating")
        suffix = f" (prev: {prev})" if prev else ""
        p = doc.add_paragraph()
        run = p.add_run(f"Rating: {rating}{suffix}")
        run.bold = True
        return
    if btype == "metric_cards":
        metrics = block.get("metrics") or []
        if metrics:
            tbl = doc.add_table(rows=len(metrics), cols=2)
            tbl.style = "Light Grid Accent 1"
            for i, m in enumerate(metrics):
                tbl.rows[i].cells[0].text = str(m.get("label", ""))
                value = str(m.get("value", ""))
                delta = m.get("delta")
                if delta:
                    value = f"{value}  ({delta})"
                tbl.rows[i].cells[1].text = value
        return
    if btype == "table":
        title = block.get("title")
        if title:
            p = doc.add_paragraph()
            run = p.add_run(str(title))
            run.bold = True
        headers = block.get("headers") or []
        rows = block.get("rows") or []
        if not headers:
            return
        tbl = doc.add_table(rows=1, cols=len(headers))
        tbl.style = "Table Grid"
        hdr_cells = tbl.rows[0].cells
        for i, h in enumerate(headers):
            hdr_cells[i].text = str(h.get("label", ""))
        for row in rows:
            row_cells = tbl.add_row().cells
            for i, h in enumerate(headers):
                key = h.get("key", "")
                val = row.get(key, "")
                row_cells[i].text = "" if val is None else str(val)
        for fn in block.get("footnotes") or []:
            p = doc.add_paragraph()
            run = p.add_run(str(fn))
            run.italic = True
        return
    if btype == "bullet_list":
        for item in block.get("items") or []:
            doc.add_paragraph(str(item), style="List Bullet")
        return
    if btype in ("pull_quote", "quote"):
        content = str(block.get("content") or block.get("text") or "")
        p = doc.add_paragraph(content, style="Intense Quote")
        attribution = block.get("attribution") or block.get("source")
        if attribution:
            p2 = doc.add_paragraph(f"— {attribution}")
            for run in p2.runs:
                run.italic = True
        return
    if btype == "callout_grid":
        items = block.get("items") or []
        if items:
            cols = 2
            rows = (len(items) + cols - 1) // cols
            tbl = doc.add_table(rows=rows, cols=cols)
            tbl.style = "Light Shading"
            for idx, item in enumerate(items):
                r, c = divmod(idx, cols)
                cell = tbl.rows[r].cells[c]
                head = str(item.get("title") or "")
                body = str(item.get("body") or item.get("content") or "")
                cell.text = f"{head}\n{body}" if head else body
        return
    if btype == "timeline":
        for event in block.get("events") or []:
            date = str(event.get("date") or "")
            content = str(event.get("content") or event.get("title") or "")
            doc.add_paragraph(f"{date}: {content}", style="List Bullet")
        return
    if btype == "comparison_split":
        cols = block.get("columns") or []
        if len(cols) == 2:
            tbl = doc.add_table(rows=1, cols=2)
            tbl.style = "Table Grid"
            for i, col in enumerate(cols):
                head = str(col.get("title") or "")
                body = str(col.get("body") or col.get("content") or "")
                tbl.rows[0].cells[i].text = f"{head}\n\n{body}" if head else body
        return
    if btype == "group":
        for child_idx, child in enumerate(block.get("blocks") or []):
            _render_block(
                doc, child, path=f"{path}.{child_idx}", chart_pngs=chart_pngs
            )
        return
    # Unknown block: italic placeholder
    p = doc.add_paragraph()
    run = p.add_run(f"[{btype}]")
    run.italic = True
```

- [ ] **Step 3: Run test; iterate until it passes**

```bash
uv run pytest packages/server/tests/services/test_report_docx.py -v
```

- [ ] **Step 4: Add tests for each block type, table, metric_cards, comparison_split, callout_grid, timeline, group recursion, and missing-chart-png fallback**

For each block type, one test that asserts the output contains the expected text or has the expected number of tables/paragraphs.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check packages/server/src/openlia_server/services/report_docx.py
uv run ruff format packages/server/src/openlia_server/services/report_docx.py
git add packages/server/src/openlia_server/services/report_docx.py packages/server/tests/services/test_report_docx.py
git commit -m "feat(reports): hybrid Word-native DOCX assembler with embedded chart PNGs"
```

### Task 4.4 — Wire DOCX route to the new pipeline

Rename `/{report_id}/docx` to `/{report_id}/export/docx` for symmetry with the PDF route, and have it call `capture_chart_pngs` + `assemble_docx` + derived-title filename.

- [ ] **Step 1: Write failing route test**

```python
# packages/server/tests/routes/test_reports_docx.py
def test_docx_route_returns_docx_with_derived_title(
    authed_client, seeded_report_id, monkeypatch
):
    from openlia_server.services import report_export

    async def fake_capture(*args, **kwargs):
        return {"0-0": b"PNG"}

    monkeypatch.setattr(report_export, "capture_chart_pngs", fake_capture)

    app = authed_client.app
    app.state.render_base_url_resolver = type(
        "R", (), {"resolve": lambda self: "http://test", "invalidate": lambda self: None}
    )()

    resp = authed_client.get(f"/api/reports/{seeded_report_id}/export/docx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in resp.headers["content-disposition"]
```

Run: `uv run pytest packages/server/tests/routes/test_reports_docx.py -v` → FAIL.

- [ ] **Step 2: Replace the DOCX route body**

In `packages/server/src/openlia_server/routes/reports.py`, replace the existing `/{report_id}/docx` handler with `/{report_id}/export/docx`:

```python
@router.get("/{report_id}/export/docx")
async def export_report_docx_route(
    report_id: str,
    request: Request,
    user: User = require_auth,
    session: DBSession = Depends(session_dep),
) -> Response:
    try:
        schema = get_report(session, report_id=report_id, user_id=user.id)
    except ReportNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc

    launcher = getattr(request.app.state, "browser_launcher", None)
    if launcher is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DOCX export unavailable (browser launcher not configured)",
        )
    resolver = getattr(request.app.state, "render_base_url_resolver", None)
    base_url = resolver.resolve() if resolver else None
    if base_url is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Report rendering requires a built frontend or running Vite dev server.",
        )

    payload = schema.model_dump(mode="json")
    cookies = _forward_session_cookie(request, base_url)
    bundle_url = f"{base_url}/reports/{report_id}/render"

    try:
        chart_pngs = await capture_chart_pngs(
            launcher, bundle_url=bundle_url, cookies=cookies
        )
    except Exception as exc:
        if resolver:
            resolver.invalidate()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"DOCX chart capture failed: {exc}",
        ) from exc

    title = derive_report_title(payload.get("mode"), schema)
    docx_bytes = assemble_docx(
        payload, chart_pngs=chart_pngs, header_text=title
    )
    filename = _sanitize_filename(f"{title}.docx")
    return Response(
        content=docx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={
            "content-disposition": f'attachment; filename="{filename}"; '
            f"filename*=UTF-8''{urlquote(filename)}"
        },
    )
```

Extract `_forward_session_cookie(request, base_url) -> list[dict] | None` as a helper shared between the PDF and DOCX handlers — pull the cookie-building code out of the PDF handler into this helper.

- [ ] **Step 3: Update the old `/{report_id}/docx` to redirect to the new path (3-day grace period, then delete in a follow-up)**

```python
@router.get("/{report_id}/docx")
async def export_report_docx_redirect(report_id: str) -> Response:
    return RedirectResponse(url=f"./{report_id}/export/docx", status_code=308)
```

Actually — since no external clients use this URL (only the frontend, which we control), **just delete the old route**. Saves complexity.

- [ ] **Step 4: Update `frontend/src/api/reports.ts:279`** (and any callers) so `reportDocxUrl` returns the new path

```typescript
export function reportDocxUrl(reportId: string): string {
  return `/api/reports/${reportId}/export/docx`;
}
```

Update the existing test in `frontend/src/api/__tests__/reports.test.ts` accordingly.

- [ ] **Step 5: Verify both backend and frontend tests pass; commit**

```bash
uv run pytest packages/server/tests/routes/test_reports_docx.py -v
cd frontend && npm run test -- src/api/__tests__/reports.test.ts
cd /Users/tkchang/Projects/OpenLIA
git add -u
git commit -m "feat(reports): SPA-driven DOCX export with chart screenshots and derived filename"
```

### Task 4.5 — Flip the feature flag

- [ ] **Step 1: Set `VITE_REPORT_DOCX_ENABLED=true` as the build default**

In `frontend/.env` (or `frontend/.env.development` and `frontend/.env.production`), add:

```
VITE_REPORT_DOCX_ENABLED=true
```

If those files don't exist, document the flag in `frontend/README.md` and have the dev script export it.

- [ ] **Step 2: Manual smoke**

Restart Vite. Open Repository → download dropdown → "Download as Word" appears. Click → DOCX downloads → open in Word → cover page styled, sections present, charts inlined as images, page numbers in footer.

- [ ] **Step 3: Commit**

```bash
git add frontend/.env*
git commit -m "feat(reports): enable DOCX option in download dropdown"
```

---

## Phase 5 — Drop Markdown path

**Files involved:**
- Modify: `packages/server/src/openlia_server/routes/files.py:34-51` (delete download route)
- Modify: `packages/server/src/openlia_server/services/files.py:71-105` (delete `resolve_report_download`)
- Modify: `frontend/src/api/files.ts` (delete `downloadUrlForReport`)
- Modify: `packages/server/src/openlia_server/services/reports.py` (stop populating `content_markdown` at create_report)

`content_markdown` column on `Report` model stays for now (avoid a migration); it's just orphaned data going forward.

### Task 5.1 — Delete backend MD route

- [ ] **Step 1: Confirm no callers**

```bash
grep -rn "downloadUrlForReport\|/reports/.*/download" frontend/src/ packages/server/src/
```

After Phase 3, the only remaining reference should be `frontend/src/api/files.ts` itself (the helper we're about to remove) and possibly `frontend/src/components/viewer/renderers/sourceUrl.ts:6`. If `sourceUrl.ts` still uses it, update that surface to use the new shared download button or remove the call site.

- [ ] **Step 2: Write a failing test that the route returns 404**

```python
# packages/server/tests/routes/test_files_download.py
def test_md_download_route_returns_404(authed_client, seeded_report_id):
    resp = authed_client.get(f"/api/reports/{seeded_report_id}/download")
    assert resp.status_code == 404
    resp2 = authed_client.get(
        f"/api/reports/{seeded_report_id}/download?format=md"
    )
    assert resp2.status_code == 404
```

Expected: FAIL (route still exists).

- [ ] **Step 3: Delete the route handler in `files.py`, the `resolve_report_download` service in `services/files.py`, and the `UnsupportedFormat` exception if it's no longer used**

Update any imports.

- [ ] **Step 4: Verify; commit**

```bash
uv run pytest packages/server/tests/routes/test_files_download.py -v
git add -u
git commit -m "refactor(reports): delete markdown download route and resolve_report_download service"
```

### Task 5.2 — Delete frontend MD API helper

- [ ] **Step 1: Delete `downloadUrlForReport` from `frontend/src/api/files.ts`**

Keep `downloadUrlForAttachment` (different feature).

- [ ] **Step 2: Update any remaining importers**

`frontend/src/components/viewer/renderers/sourceUrl.ts` currently imports `downloadUrlForReport`. If that file is still used after Phase 3, update its `kind === "report"` branch to return `null` or a route that opens the report in the viewer (not a download URL).

- [ ] **Step 3: Run typecheck and tests**

```bash
cd frontend && npm run typecheck && npm run test
```

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor(reports): drop downloadUrlForReport from frontend API"
```

### Task 5.3 — Stop populating `content_markdown` on create

- [ ] **Step 1: Find writers**

```bash
grep -n "content_markdown" packages/server/src/openlia_server/services/reports.py
```

- [ ] **Step 2: Remove the field from `create_report`'s `Report(...)` construction**

Leave the column on the model (`content.py`) untouched — it stays as nullable orphan data. Removing the column is a future cleanup that needs an Alembic migration; out of scope here.

- [ ] **Step 3: Update tests in `packages/server/tests/services/test_report_store.py` that assert `content_markdown` is set**

If any test reads back `content_markdown`, change it to assert it's `None` or empty string. Don't delete the test — re-purpose it to document the new contract.

- [ ] **Step 4: Run report-store tests; commit**

```bash
uv run pytest packages/server/tests/services/test_report_store.py -v
git add -u
git commit -m "refactor(reports): stop writing content_markdown on create (column kept for now)"
```

---

## Phase 6 — Final verification

- [ ] **Step 1: Run full backend suite**

```bash
uv run pytest packages/server/tests/ packages/core/tests/ -x
```

Expected: green except the 2 pre-existing migration test failures.

- [ ] **Step 2: Run full frontend suite**

```bash
cd frontend && npm run test && npm run typecheck && npm run build
```

Expected: green except 2 pre-existing SettingsShellBlocker failures.

- [ ] **Step 3: Lint clean**

```bash
cd /Users/tkchang/Projects/OpenLIA
uv run ruff check . && uv run ruff format --check .
```

- [ ] **Step 4: Manual end-to-end smoke (the most important check — UI quality is what triggered this work)**

Walk through every surface in dev:
- Open server: `uv run openlia serve`
- Open Vite: `cd frontend && npm run dev`
- Visit Repository → download a report as PDF → open the file. Confirm: vector charts visible, full styling, filename uses subject (e.g., "AAPL — Initiation.pdf").
- Same row, download as Word → open in Word. Confirm: cover page styled, charts inlined as images, native page numbers in footer, TOC visible (right-click to update).
- Open the same report in FileViewer → download from toolbar → same checks.
- In equity research, generate a report → ReportCard download → same checks.
- In morning briefing, open hero card and report card downloads → same checks.
- In earnings update, click the download → same checks.

If anything looks "cheap" (the original complaint), debug before declaring done.

- [ ] **Step 5: Open PR**

Use the existing PR conventions seen in `git log` (`fix(reports):`, `feat(reports):`). Reference all 5 phases in the PR body.

---

## Out of scope (documented, not done)

- **Caching generated PDFs/DOCXs.** Each download regenerates. Add later if perf complaints arise. Suggested approach: filesystem cache at `~/.openlia/exports/{report_id}.{fmt}`, invalidated when schema changes.
- **Removing the `content_markdown` column.** Requires an Alembic migration. Leave for a cleanup PR.
- **Bulk-download zip from Repository.** Not asked for. Easy follow-up if needed.
- **Print preview button.** Browser's native Cmd+P already works on the print page route; no in-app button needed.

---

## Self-review checklist (run before handoff)

1. Every chunk in the user's stated order (PDF fix → component → surfaces → DOCX → drop MD) has explicit tasks. ✓
2. Filename uses `derive_report_title()`. ✓ (Tasks 1.3, 4.4)
3. SPA-only PDF — static fallback deleted. ✓ (Task 1.3)
4. DOCX hybrid layout with chart PNGs at 2× DPI, 6.5" wide. ✓ (Tasks 4.2, 4.3)
5. Dev-mode auto-detect (env → dist → Vite probe). ✓ (Task 1.1)
6. Shared `<ReportDownloadButton>` on every surface. ✓ (Tasks 2.2, 3.1–3.6)
7. In-app fetch with button spinner + toast on error. ✓ (Tasks 2.1, 2.2)
8. DOCX feature-flagged off until Phase 4. ✓ (Tasks 2.2, 4.5)
9. MD path fully removed (UI + backend route + service). ✓ (Phase 5)
10. Every step shows real code; no "TBD" / "similar to". ✓
