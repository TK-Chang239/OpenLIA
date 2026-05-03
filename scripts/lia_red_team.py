#!/usr/bin/env python3
"""Lia red-team harness (Component G.2).

Drives the local chat API for every (department x prompt) pair, captures
the streamed response, joins the audit-log rows for that session, and
writes a markdown review file.

Usage:
    uv run python scripts/lia_red_team.py --out /tmp/redteam-2026-05-03.md

Assumes:
- `uv run openlia serve` is running on localhost:8000.
- Mode is personal (no auth needed). Company-mode adaptation is a follow-on.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

CORPUS_PATH = Path("docs/lia_red_team_corpus.md")
DEFAULT_BASE = "http://localhost:8000"

DEPARTMENTS = (
    "secretary",
    "equity_research",
    "earnings_update",
    "morning_briefing",
    "macro_research",
    "retail_sentiment",
    "panic_thermometer",
)


@dataclass
class Prompt:
    id: str
    category: str
    prompt: str


def parse_corpus(text: str) -> list[Prompt]:
    """Parse the markdown corpus into Prompt objects."""
    out: list[Prompt] = []
    current_category: str | None = None
    in_yaml = False
    buf: list[str] = []
    for line in text.splitlines():
        h = re.match(r"^##\s+(.+?)\s*\(\d+\)\s*$", line)
        if h:
            current_category = h.group(1).strip()
            continue
        if line.strip().startswith("```yaml"):
            in_yaml, buf = True, []
            continue
        if in_yaml and line.strip() == "```":
            in_yaml = False
            block = "\n".join(buf)
            for m in re.finditer(r'-\s*id:\s*(\S+)\s+prompt:\s*"((?:[^"\\]|\\.)*)"', block):
                out.append(
                    Prompt(
                        id=m.group(1),
                        category=current_category or "?",
                        prompt=m.group(2).replace('\\"', '"'),
                    )
                )
            continue
        if in_yaml:
            buf.append(line)
    return out


def create_session(client: httpx.Client, base: str, department: str) -> str:
    r = client.post(f"{base}/api/chat/sessions", json={"department": department})
    r.raise_for_status()
    return r.json()["id"]


def stream_chat(
    client: httpx.Client,
    base: str,
    session_id: str,
    prompt: str,
) -> tuple[str, list[dict]]:
    """Returns (assistant_text, guardrail_events)."""
    text_chunks: list[str] = []
    guardrails: list[dict] = []
    with client.stream(
        "GET",
        f"{base}/api/chat/sessions/{session_id}/stream",
        params={"q": prompt},
    ) as r:
        r.raise_for_status()
        current_event: str | None = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                current_event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
                if current_event == "chat.token":
                    text_chunks.append(payload.get("text", ""))
                elif current_event == "chat.guardrail":
                    guardrails.append(payload)
                elif current_event == "chat.done":
                    break
    return "".join(text_chunks), guardrails


def fetch_audit(client: httpx.Client, base: str, session_id: str) -> list[dict]:
    r = client.get(f"{base}/api/admin/guardrail-events", params={"since_days": 1})
    r.raise_for_status()
    items = r.json()["items"]
    return [it for it in items if it["session_id"] == session_id]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--departments", nargs="+", default=list(DEPARTMENTS))
    args = ap.parse_args()

    prompts = parse_corpus(CORPUS_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(prompts)} prompts; running against {len(args.departments)} desks.")

    out_lines: list[str] = [f"# Lia Red-Team Run - {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
    with httpx.Client(timeout=120.0) as client:
        for dept in args.departments:
            out_lines.append(f"\n## Desk: {dept}\n")
            by_cat: dict[str, list[Prompt]] = {}
            for p in prompts:
                by_cat.setdefault(p.category, []).append(p)
            for cat, plist in by_cat.items():
                out_lines.append(f"\n### Category: {cat}\n")
                for p in plist:
                    print(f"  [{dept}] {p.id} ...", flush=True)
                    try:
                        sid = create_session(client, args.base, dept)
                        text, guardrails = stream_chat(client, args.base, sid, p.prompt)
                        audit = fetch_audit(client, args.base, sid)
                    except Exception as exc:
                        text, guardrails, audit = f"[ERROR {exc!r}]", [], []
                    cats = json.dumps([g.get("category") for g in guardrails])
                    out_lines.append(
                        f"\n#### {p.id}\n"
                        f"**Prompt:** {p.prompt}\n\n"
                        f"**Response:**\n\n```\n{text}\n```\n\n"
                        f"**Guardrail events:** {len(guardrails)}  `{cats}`\n\n"
                        f"**Audit rows:** {len(audit)}\n\n"
                        f"- [ ] PASS  - [ ] FAIL - reviewer notes:\n"
                    )
    args.out.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"Wrote: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
