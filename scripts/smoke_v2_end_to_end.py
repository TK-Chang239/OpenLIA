"""Live end-to-end smoke for the equity-research v2.2 pipeline.

Runs the FastAPI app in-process against a temp SQLite database, POSTs to
``/api/departments/equity-research/v2/report`` for AAPL, drains the SSE
stream, and exits 0 once a ``completed`` frame with non-empty HTML
arrives. Any other terminal state (``failed``) prints the reason and
exits non-zero so the build-fix loop can pick it up.

Reads API keys from the repository ``.env`` file at project root.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        print(f"smoke: no .env at {env_path}", file=sys.stderr)
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    current_event: str | None = None
    data_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: ") :].strip()
        elif line.startswith("data: "):
            data_lines.append(line[len("data: ") :])
        elif line == "":
            if current_event is not None:
                payload = "\n".join(data_lines)
                try:
                    parsed = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    parsed = {"_raw": payload}
                frames.append((current_event, parsed))
            current_event = None
            data_lines = []
    if current_event is not None:
        payload = "\n".join(data_lines)
        try:
            parsed = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            parsed = {"_raw": payload}
        frames.append((current_event, parsed))
    return frames


def _seed_user(session_factory) -> None:
    from openlia_server.db.models.auth import User

    with session_factory() as s:
        existing = s.query(User).filter(User.id == "local").one_or_none()
        if existing is not None:
            return
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()


def main() -> int:
    _load_dotenv()

    # Force the v2 factory to use a deterministic provider for the smoke run.
    # Anthropic is preferred (project's primary). Toggle via
    # OPENLIA_V2_LLM_KIND=openai if you want to swap.
    os.environ.setdefault("OPENLIA_V2_LLM_KIND", "anthropic")
    os.environ["OPENLIA_MODE"] = "personal"

    tmp_db = REPO_ROOT / ".smoke_v2.db"
    if tmp_db.exists():
        tmp_db.unlink()
    os.environ["OPENLIA_DB_URL"] = f"sqlite:///{tmp_db}"

    # Imports are delayed so env vars land first.
    import openlia_server.db.models.register_all  # noqa: F401 — ORM registration
    from fastapi.testclient import TestClient
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.db.base import Base

    session_mod.configure_engine(os.environ["OPENLIA_DB_URL"])
    Base.metadata.create_all(session_mod.get_engine())
    _seed_user(session_mod.SessionLocal)

    app = create_app(db_session_factory=session_mod.SessionLocal)
    client = TestClient(app)

    payload = {
        "user_input": (
            "Generate an equity research report on AAPL covering the"
            " investment thesis, recent developments, financials, valuation,"
            " and key risks."
        ),
        "report_template_id": "stock_research_v2",
        "composer_inputs": {"ticker": "AAPL"},
    }

    print(f"smoke: starting v2 run at {datetime.now(UTC).isoformat()}", flush=True)
    started = time.monotonic()
    resp = client.post(
        "/api/departments/equity-research/v2/report",
        json=payload,
        timeout=600,
    )
    elapsed = time.monotonic() - started

    print(f"smoke: HTTP {resp.status_code} after {elapsed:.1f}s", flush=True)
    if resp.status_code != 200:
        print(f"smoke: body {resp.text[:2000]}", file=sys.stderr)
        return 2

    frames = _parse_sse(resp.text)
    print(f"smoke: parsed {len(frames)} SSE frames", flush=True)
    for event, data in frames:
        snippet = json.dumps(data)[:200]
        print(f"  - {event}: {snippet}", flush=True)

    terminals = [(e, d) for e, d in frames if e in ("completed", "failed")]
    if not terminals:
        print("smoke: NO terminal frame", file=sys.stderr)
        return 3

    event, data = terminals[-1]
    if event == "failed":
        print(
            f"smoke: FAILED stage={data.get('stage')!r} reason={data.get('reason')!r}",
            file=sys.stderr,
        )
        return 4

    html = data.get("html") or ""
    if not html.strip():
        print("smoke: completed but HTML body empty", file=sys.stderr)
        return 5

    print(f"smoke: COMPLETED — html length={len(html)} chars", flush=True)
    print(f"smoke: html preview: {html[:600]}...", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
