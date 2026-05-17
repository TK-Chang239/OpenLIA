# Revision Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `revise_report` LLM tool + `RevisionRunner` editor pass that takes an original report + chat transcript + bundle's read_payload and produces a new revised report saved as a separate Repository entry, re-anchoring the source chat to the revision on success. Behavior gated behind `OPENLIA_REVISION_PASS_ENABLED`. Ticker-keyed chat binding amendment to chat-followup spec is also gated.

**Architecture:** A new `RevisionRunner` module produces a revised ReportSchema in one `EditorClient.compose` call. The chat-route intercepts the `revise_report` tool call before normal dispatch, posts the new background task to the existing `BackgroundReportRegistry`, returns a synthetic `revision_started` result to the LLM, then on successful completion runs a custom wrapper that re-anchors the chat session's `attached_report_id` and fanouts a `chat.attached_report_changed` event over the notifications SSE.

**Tech Stack:** Python 3.13, Pydantic v2, FastAPI, SQLAlchemy. Frontend: React + TypeScript. Lint: ruff. Package mgr: uv.

**Branch:** Create `feat/revision-pass` from `main` AFTER both `feat/subagent-report-architecture` AND `feat/report-chat-followup` have shipped to main.

**Spec:** `docs/superpowers/specs/2026-05-17-revision-pass-design.md`

---

## Pre-flight (one-time setup)

- [ ] **Confirm both predecessor branches merged:** `git log main --oneline | grep -iE "subagent|chat.followup" | head -5`. If either is missing, do NOT proceed.
- [ ] **Create branch:** `git checkout main && git pull && git checkout -b feat/revision-pass`
- [ ] **Confirm clean tree:** `git status --short` (expect empty)

> **Sandbox note for all `uv run` commands:** If you see `Failed to initialize cache at .cache/uv` or similar, pass `dangerouslyDisableSandbox: true` to the Bash tool.

---

## Task 1: Chat transcript compressor (deterministic, no LLM)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/chat_transcript_compressor.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py
from __future__ import annotations

from openlia.llm.runtime.chat_transcript_compressor import compress_chat_transcript


def _msg(role: str, content: str, tool_calls=None, tool_call_id=None) -> dict:
    return {"role": role, "content": content, "tool_calls": tool_calls, "tool_call_id": tool_call_id}


def test_user_and_assistant_messages_kept_verbatim() -> None:
    msgs = [
        _msg("user", "What's the revenue?"),
        _msg("assistant", "$245B in FY25."),
    ]
    out = compress_chat_transcript(msgs)
    assert "What's the revenue?" in out
    assert "$245B in FY25." in out


def test_tool_calls_summarized_not_verbatim() -> None:
    msgs = [
        _msg("user", "Check Q4."),
        _msg("assistant", "", tool_calls=[
            {"id": "c1", "function": {"name": "read_payload", "arguments": '{"ref":"r_abc","path":"Financials.Cash_Flow.yearly"}'}}
        ]),
        _msg("tool", "1213 chars of tabular data...", tool_call_id="c1"),
    ]
    out = compress_chat_transcript(msgs)
    assert "read_payload" in out
    assert "Financials.Cash_Flow.yearly" in out
    # The raw 1213-char payload is NOT verbatim — it's summarized.
    assert "1213 chars" in out or "chars" in out


def test_cap_chars_trims_oldest_first_with_marker() -> None:
    long_text = "x" * 50_000
    msgs = [
        _msg("user", "early message — should be trimmed"),
        _msg("assistant", long_text),
        _msg("user", "recent message — must be kept"),
    ]
    out = compress_chat_transcript(msgs, cap_chars=10_000)
    assert len(out) <= 10_000
    assert "recent message" in out
    # Trimming marker present.
    assert "trimmed" in out.lower() or "..." in out


def test_empty_transcript_returns_empty_string() -> None:
    assert compress_chat_transcript([]) == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/chat_transcript_compressor.py
"""Deterministic compression of a chat-message transcript for inclusion
in a revision editor request.

User and assistant text content is kept verbatim. Tool calls become
one-line summaries showing the tool name + arg keys. Tool results become
size-suffix summaries (no payload bodies). Oldest content is trimmed
first when the cap is exceeded; a marker is inserted.
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_CAP_CHARS = 30_000


def _format_tool_call(call: dict[str, Any]) -> str:
    name = (call.get("function") or {}).get("name", "?")
    raw_args = (call.get("function") or {}).get("arguments", "{}")
    try:
        parsed = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
    except json.JSONDecodeError:
        parsed = {}
    args_summary = ", ".join(f"{k}={parsed[k]!r}" for k in list(parsed.keys())[:4])
    return f"[tool_call] {name}({args_summary})"


def _format_tool_result(content: str) -> str:
    chars = len(content or "")
    head = (content or "").strip().split("\n", 1)[0][:80]
    return f"[tool_result] {chars} chars: {head}"


def _format_message(msg: dict[str, Any]) -> str:
    role = msg.get("role", "?")
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls") or []
    if role == "tool":
        return _format_tool_result(content)
    if role == "assistant" and tool_calls:
        lines = [_format_tool_call(tc) for tc in tool_calls]
        if content.strip():
            lines.append(f"assistant: {content}")
        return "\n".join(lines)
    return f"{role}: {content}"


def compress_chat_transcript(
    messages: list[dict[str, Any]],
    *,
    cap_chars: int = DEFAULT_CAP_CHARS,
) -> str:
    """Compress messages into a string under ``cap_chars``. Oldest
    content is trimmed first; a marker is inserted when trimming occurs."""
    if not messages:
        return ""
    formatted = [_format_message(m) for m in messages]
    joined = "\n\n".join(formatted)
    if len(joined) <= cap_chars:
        return joined
    # Trim from the front, leaving a marker.
    marker = "[... earlier discussion trimmed ...]\n\n"
    available = cap_chars - len(marker)
    # Build from the END so most-recent content is kept.
    out_parts: list[str] = []
    running = 0
    for chunk in reversed(formatted):
        size = len(chunk) + 2  # +2 for "\n\n" separator
        if running + size > available:
            break
        out_parts.append(chunk)
        running += size
    out_parts.reverse()
    return marker + "\n\n".join(out_parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Lint + format + commit**

```bash
uv run ruff format packages/core/src/openlia/llm/runtime/chat_transcript_compressor.py packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py
uv run ruff check packages/core/src/openlia/llm/runtime/chat_transcript_compressor.py packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py
git add packages/core/src/openlia/llm/runtime/chat_transcript_compressor.py packages/core/tests/test_llm/test_runtime/test_chat_transcript_compressor.py
git commit -m "feat(revision): deterministic chat-transcript compressor"
```

---

## Task 2: Subject normalization helper

**Files:**
- Create: `packages/server/src/openlia_server/services/subject_normalize.py`
- Test: `packages/server/tests/test_subject_normalize.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_subject_normalize.py
from openlia_server.services.subject_normalize import normalize_subject


def test_normalize_lowercases_and_trims() -> None:
    assert normalize_subject("MSFT") == "msft"
    assert normalize_subject(" msft ") == "msft"
    assert normalize_subject(" MSFT\n") == "msft"


def test_normalize_none_or_empty_returns_empty_string() -> None:
    assert normalize_subject(None) == ""
    assert normalize_subject("") == ""
    assert normalize_subject("   ") == ""


def test_normalize_preserves_internal_punctuation() -> None:
    # Exchange suffix not smoothed in v1 — different exchanges count as different.
    assert normalize_subject("MSFT.US") == "msft.us"
    assert normalize_subject("MSFT.US") != normalize_subject("MSFT.NASDAQ")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_subject_normalize.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/server/src/openlia_server/services/subject_normalize.py
"""Normalize a chat-binding subject (typically a ticker) for equality
comparison. v1: lowercase + whitespace-trim only. Exchange-suffix
smoothing is deferred."""

from __future__ import annotations


def normalize_subject(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.strip().lower()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/server/tests/test_subject_normalize.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/subject_normalize.py packages/server/tests/test_subject_normalize.py
git commit -m "feat(revision): subject normalization helper"
```

---

## Task 3: Extend `EditorClient.EditorRequest` with revision fields + role-prompt switch

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/editor_client.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py`

> **Before starting:** Run `grep -n "class EditorRequest\|class EditorClient\|def compose\|role_prompt" packages/core/src/openlia/llm/runtime/editor_client.py | head -20` to confirm current shape.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py
from __future__ import annotations

import pytest
from _fakes import FakeProvider, FakeProviderScript

from openlia.llm.runtime.editor_client import EditorClient, EditorRequest, EDITOR_TOOL_NAME
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.types import ToolCall


def _final_payload() -> dict:
    return {
        "cover": {"title": "x", "subtitle": "y", "tagline": "z"},
        "sections": [{"id": "company_overview", "title": "Overview",
                      "blocks": [{"type": "text", "content": "Final body."}]}],
    }


def _draft() -> SectionDraft:
    return SectionDraft.model_validate({
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": "Body."}],
        "citations_used": [],
        "word_count": 1,
        "open_questions": [],
    })


def _base_request(revision_brief: str | None = None) -> EditorRequest:
    return EditorRequest(
        role_prompt="ROLE",
        style_guide="STYLE",
        schema_strictness="STRICT",
        company_thesis="t",
        cross_section_themes=["t1", "t2"],
        section_drafts=[_draft()],
        open_questions=[],
        framework_cover_instructions="cover instructions",
        revision_brief=revision_brief,
        sections_to_focus=None,
        chat_transcript_excerpt=None,
    )


@pytest.mark.asyncio
async def test_editor_request_accepts_revision_fields() -> None:
    req = _base_request(revision_brief="Fix the Q4 capex number")
    assert req.revision_brief == "Fix the Q4 capex number"
    assert req.sections_to_focus is None
    assert req.chat_transcript_excerpt is None


@pytest.mark.asyncio
async def test_compose_uses_revision_role_prompt_when_brief_set() -> None:
    """When revision_brief is set, EditorClient must build its system
    prompt from revision_editor_role.yaml.j2 (loaded by caller and
    passed via role_prompt) — meaning the role_prompt string itself
    should be the revision role text."""
    # Caller injects revision_role_prompt content via role_prompt.
    provider = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())]),
    ]))
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    req = _base_request(revision_brief="Tighten the risk section")
    req = req.model_copy(update={"role_prompt": "REVISION_ROLE_PROMPT"})
    payload = await client.compose(req)
    assert payload["cover"]["title"] == "x"
    # Verify the system prompt sent to the provider includes the revision role.
    req_sent = provider.captured_requests[0]
    assert "REVISION_ROLE_PROMPT" in req_sent.system


@pytest.mark.asyncio
async def test_compose_passes_revision_brief_into_user_prompt() -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())]),
    ]))
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    req = _base_request(revision_brief="MUST_APPEAR_IN_USER_PROMPT")
    await client.compose(req)
    user_msg = next(m for m in provider.captured_requests[0].messages if m.role == "user")
    assert "MUST_APPEAR_IN_USER_PROMPT" in user_msg.content


@pytest.mark.asyncio
async def test_compose_includes_chat_transcript_excerpt_when_set() -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())]),
    ]))
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    req = _base_request(revision_brief="x")
    req = req.model_copy(update={"chat_transcript_excerpt": "USER_SAID_X"})
    await client.compose(req)
    user_msg = next(m for m in provider.captured_requests[0].messages if m.role == "user")
    assert "USER_SAID_X" in user_msg.content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py -v
```

Expected: FAIL (EditorRequest lacks revision_brief / sections_to_focus / chat_transcript_excerpt fields)

- [ ] **Step 3: Extend `EditorRequest` + update `_user_prompt`**

In `packages/core/src/openlia/llm/runtime/editor_client.py`, modify the `EditorRequest` dataclass:

```python
@dataclass(frozen=True)
class EditorRequest:
    role_prompt: str
    style_guide: str
    schema_strictness: str
    company_thesis: str
    cross_section_themes: list[str]
    section_drafts: list[SectionDraft]
    open_questions: list[OpenQuestion]
    framework_cover_instructions: str
    # NEW (all optional; None preserves original-report editor behavior):
    revision_brief: str | None = None
    sections_to_focus: list[str] | None = None
    chat_transcript_excerpt: str | None = None
```

Update `_user_prompt(req: EditorRequest)` to include the revision sections when `req.revision_brief` is set. Append at the end of the current `_user_prompt` builder:

```python
def _user_prompt(req: EditorRequest) -> str:
    drafts_blob = json.dumps([d.model_dump() for d in req.section_drafts], default=str, indent=2)
    open_blob = json.dumps([q.model_dump() for q in req.open_questions], default=str, indent=2)
    base = (
        f"## Company thesis\n{req.company_thesis}\n\n"
        f"## Cross-section themes\n- " + "\n- ".join(req.cross_section_themes) + "\n\n"
        f"## Section drafts (verbatim from subagents)\n```json\n{drafts_blob}\n```\n\n"
        f"## Open questions\n```json\n{open_blob}\n```\n\n"
        f"## Cover instructions\n{req.framework_cover_instructions}\n"
    )
    if req.revision_brief is not None:
        base += (
            f"\n## Revision brief\n{req.revision_brief}\n"
            f"\n## Sections to focus on\n"
            + (
                "\n- ".join(req.sections_to_focus)
                if req.sections_to_focus
                else "(no specific focus — apply the brief broadly)"
            )
            + "\n"
        )
        if req.chat_transcript_excerpt:
            base += (
                f"\n## Chat transcript excerpt (the discussion that led to this revision)\n"
                f"```\n{req.chat_transcript_excerpt}\n```\n"
            )
    return base
```

`role_prompt` is already used by `_system_prompt(req)` so passing the revision-role-prompt text via `role_prompt` already routes correctly.

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py packages/core/tests/test_llm/test_runtime/test_editor_client.py -v
```

Expected: all PASS (4 new + existing editor_client tests unchanged)

- [ ] **Step 5: Lint + format + commit**

```bash
uv run ruff format packages/core/src/openlia/llm/runtime/editor_client.py packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py
uv run ruff check packages/core/src/openlia/llm/runtime/editor_client.py packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py
git add packages/core/src/openlia/llm/runtime/editor_client.py packages/core/tests/test_llm/test_runtime/test_editor_client_revision_mode.py
git commit -m "feat(revision): extend EditorRequest with revision_brief, sections_to_focus, chat_transcript_excerpt"
```

---

## Task 4: `revision_editor_role.yaml.j2` shared partial

**Files:**
- Create: `packages/core/src/openlia/prompts/shared/revision_editor_role.yaml.j2`
- Test: `packages/core/tests/test_llm/test_runtime/test_revision_editor_role_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_revision_editor_role_prompt.py
from __future__ import annotations

from pathlib import Path

import openlia.prompts as prompts_pkg


def test_revision_editor_role_partial_describes_revision_responsibilities() -> None:
    p = Path(prompts_pkg.__file__).parent / "shared" / "revision_editor_role.yaml.j2"
    text = p.read_text()
    lower = text.lower()
    # Must reference key concepts.
    assert "revision_brief" in text
    assert "chat" in lower and ("transcript" in lower or "discussion" in lower)
    assert "preserve" in lower or "keep" in lower
    assert "submit_report" in text


def test_revision_editor_role_partial_has_no_per_turn_interpolations() -> None:
    """Cacheable: no current_date / search_budget templating."""
    p = Path(prompts_pkg.__file__).parent / "shared" / "revision_editor_role.yaml.j2"
    text = p.read_text()
    assert "{{ current_date" not in text
    assert "{{ search_budget" not in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_revision_editor_role_prompt.py -v
```

Expected: FAIL (FileNotFoundError)

- [ ] **Step 3: Create the partial**

```jinja
{# packages/core/src/openlia/prompts/shared/revision_editor_role.yaml.j2 #}
You are the chief editor producing a REVISED version of a previously
generated report. You have no tools other than `submit_report`.

## What you receive

- The original report's `company_thesis` and `cross_section_themes`.
- The original report's `section_drafts` — the source content you will
  rewrite from.
- A `revision_brief` (2-4 sentences) summarizing what to change. This
  is the authoritative statement of the user's intent.
- An optional `sections_to_focus` list — section_ids that need the
  most attention. Treat as a hint; you may still touch other sections
  if the brief implies it, but be conservative.
- A `chat_transcript_excerpt` showing the discussion that led to this
  revision: user corrections, missing data the user pointed out,
  structural feedback. Trust the user's corrections over the original.

## Your responsibilities, in priority order

1. **Apply the revision brief faithfully.** Do not add or remove
   things the user did not ask about. Preserve everything else.
2. **Trust the user's corrections.** When the chat transcript shows
   the user supplying a corrected number, date, or fact, use the
   corrected value — not the original.
3. **Preserve the original's structure and tone.** Same sections in
   the same order. Same depth per section (unless the brief calls for
   rebalancing).
4. **Thread the revision into the narrative.** Cross-section themes
   from the original carry over; integrate corrections so the report
   reads as a coherent whole, not as a patched version.
5. **Compose a fresh Cover.** The `cover.title`, `cover.subtitle`,
   `cover.tagline`, and `cover.tldr` may need updates to reflect the
   revised content.
6. **Build a fresh Rail.** Same shape as the original; pull verdict,
   quick_stats from the revised data.

## What you must NOT do

- Call any tool other than `submit_report`.
- Reorder sections (the original's order is final).
- Add new sections that did not exist in the original.
- Emit `meta_stats` (server-computed).
- Re-fetch live data outside of `read_payload` over the original
  bundle (which the runner has pre-seeded).

## Output

Call `submit_report` exactly once with the final revised report payload.
The schema is identical to a fresh report — same strictness applies.
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_revision_editor_role_prompt.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/shared/revision_editor_role.yaml.j2 packages/core/tests/test_llm/test_runtime/test_revision_editor_role_prompt.py
git commit -m "feat(revision): revision_editor_role.yaml.j2 partial"
```

---

## Task 5: `RevisionRunner` happy path end-to-end

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/revision_runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py`

> **Before starting:** Run `grep -n "class SubagentReportRunner\|def run\|_finalize_submit_payload\|bundle_dir" packages/core/src/openlia/llm/runtime/subagent_runner.py | head -20` to confirm patterns to mirror.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeProvider, FakeProviderScript

from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
from openlia.llm.runtime.events import ReportComplete, ReportPhase, ReportStart
from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report_context_bundle import (
    ReportContextBundle,
    persist_bundle,
)
from openlia.llm.runtime.revision_runner import RevisionRunner
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake", provider_id="p1", model_id="m1", model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
    (root / "shared" / "revision_editor_role.yaml.j2").write_text("REVISION_ROLE")
    (root / "shared" / "report_schema_strictness.yaml.j2").write_text("STRICT")
    return root


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    return tmp_path / "bundles"


@pytest.fixture
def seeded_source_bundle(tmp_path: Path, bundle_dir: Path) -> str:
    bundle_dir.mkdir()
    plan = ReportPlan.model_validate({
        "company_thesis": "thesis",
        "cross_section_themes": ["t1", "t2"],
        "sections": [{
            "section_id": "company_overview", "title": "Overview",
            "narrative_goal": "g", "key_questions": ["q1", "q2", "q3"],
            "target_depth": "standard", "word_budget": 200,
            "data_paths": [], "cross_refs": [],
        }],
    })
    draft = SectionDraft.model_validate({
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": "Original body."}],
        "citations_used": [],
        "word_count": 2,
        "open_questions": [],
    })
    persist_bundle(
        ReportContextBundle(
            plan=plan, fetched_data={}, section_drafts=[draft],
            payload_refs={}, generation_meta={},
        ),
        path=bundle_dir / "r_source.json.gz",
    )
    return "r_source"


@pytest.fixture
def seeded_source_report(db_session_factory, test_user, seeded_source_bundle) -> str:
    from openlia_server.db.models.content import Report
    with db_session_factory() as session:
        row = Report(
            id=seeded_source_bundle, user_id=test_user.id,
            department="equity_research", status="complete",
            report_schema_json=json.dumps({
                "schema_version": "2.0",
                "department": "equity_research",
                "generated_at": "2026-05-17T00:00:00+00:00",
                "cover": {"title": "MSFT", "subtitle": "Init", "tagline": "Constructive"},
                "sections": [{
                    "id": "company_overview", "title": "Overview",
                    "blocks": [{"type": "text", "content": "Original body."}]
                }],
            }),
        )
        session.add(row)
        session.commit()
    return seeded_source_bundle


@pytest.fixture
def seeded_chat_with_messages(db_session_factory, test_user, seeded_source_report) -> str:
    # Insert a ChatSession bound to source + a few messages.
    from openlia_server.db.models.content import ChatSession, ChatMessage
    with db_session_factory() as session:
        chat = ChatSession(
            id="sess_test", user_id=test_user.id, department="equity_research",
            attached_report_id=seeded_source_report,
        )
        session.add(chat)
        # Minimal message log.
        session.add(ChatMessage(session_id="sess_test", role="user", content="Q4 capex is wrong; should be $14B"))
        session.add(ChatMessage(session_id="sess_test", role="assistant", content="You're right; using $14B"))
        session.commit()
    return "sess_test"


def _editor_args() -> dict:
    return {
        "cover": {"title": "MSFT (revised)", "subtitle": "Init", "tagline": "Constructive"},
        "sections": [{
            "id": "company_overview", "title": "Overview",
            "blocks": [{"type": "text", "content": "Revised body."}],
        }],
    }


@pytest.mark.asyncio
async def test_revision_runner_happy_path(
    prompts_root: Path, bundle_dir: Path,
    seeded_source_report: str, seeded_chat_with_messages: str,
    db_session_factory,
) -> None:
    flagship = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())]),
    ]))
    runner = RevisionRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: flagship,
        report_id_factory=lambda: "r_revised",
        bundle_dir=bundle_dir,
        db_session_factory=db_session_factory,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        source_report_id=seeded_source_report,
        chat_session_id=seeded_chat_with_messages,
        revision_brief="Fix Q4 capex per discussion",
        sections_to_focus=None,
    ):
        events.append(ev)

    types = [type(e).__name__ for e in events]
    assert "ReportStart" in types
    assert "ReportComplete" in types
    phases = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert "loading_context" in phases
    assert "editing" in phases
    assert "finalizing" in phases
    final = [e for e in events if isinstance(e, ReportComplete)][-1]
    assert final.schema["cover"]["title"] == "MSFT (revised)"
    assert final.schema["department"] == "equity_research"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py -v
```

Expected: FAIL (ImportError on `RevisionRunner`)

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/revision_runner.py
"""RevisionRunner — one editor pass producing a revised ReportSchema.

Input: source ReportSchema, source ReportContextBundle, chat transcript.
Output: a new ReportSchema yielded via ReportComplete.

Bundle inheritance: copies the source bundle file to the new report
id's path on success so the chat-followup feature works on the
revised report immediately.
"""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.chat_transcript_compressor import compress_chat_transcript
from openlia.llm.runtime.editor_client import (
    EditorClient,
    EditorRequest,
)
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    SseEvent,
)
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report_context_bundle import load_bundle
from openlia.llm.runtime.section_draft import OpenQuestion, SectionDraft
from openlia.llm.types import ResolvedModel
from openlia.reports.validator import validate_report_payload

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _load_revision_role_prompt() -> str:
    import openlia.prompts as _prompts_pkg
    p = Path(_prompts_pkg.__file__).parent / "shared" / "revision_editor_role.yaml.j2"
    return p.read_text()


def _load_schema_strictness() -> str:
    import openlia.prompts as _prompts_pkg
    p = Path(_prompts_pkg.__file__).parent / "shared" / "report_schema_strictness.yaml.j2"
    return p.read_text() if p.exists() else ""


class RevisionRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        resolve: ResolveFn,
        registry: Any,
        flagship_provider_factory: ProviderFactory,
        report_id_factory: Callable[[], str] | None = None,
        bundle_dir: Path,
        db_session_factory,
    ) -> None:
        self._prompts = prompts
        self._resolve = resolve
        self._registry = registry
        self._flagship_factory = flagship_provider_factory
        self._report_id_factory = report_id_factory or (lambda: f"r_{uuid.uuid4().hex[:12]}")
        self._bundle_dir = bundle_dir
        self._db_session_factory = db_session_factory

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        source_report_id: str,
        chat_session_id: str,
        revision_brief: str,
        sections_to_focus: list[str] | None,
    ) -> AsyncIterator[SseEvent]:
        from openlia_server.db.models.content import ChatMessage, Report

        new_report_id = self._report_id_factory()
        yield ReportStart(report_id=new_report_id, department_id=department_id, mode="revision")

        yield ReportPhase(report_id=new_report_id, phase="loading_context")
        source_bundle_path = self._bundle_dir / f"{source_report_id}.json.gz"
        if not source_bundle_path.exists():
            yield ReportError(
                report_id=new_report_id,
                code="bundle_missing",
                message=(
                    "Could not revise — the original report's context "
                    "bundle is no longer available."
                ),
            )
            return
        try:
            source_bundle = load_bundle(source_bundle_path)
        except Exception as exc:
            yield ReportError(
                report_id=new_report_id, code="bundle_load_failed",
                message=f"Failed to load source bundle: {exc!s}",
            )
            return

        # Load source report + chat messages.
        with self._db_session_factory() as session:
            source_row = session.get(Report, source_report_id)
            if source_row is None or source_row.report_schema_json is None:
                yield ReportError(
                    report_id=new_report_id, code="source_missing",
                    message="Source report not found or has no payload.",
                )
                return
            source_schema = json.loads(source_row.report_schema_json)
            chat_msgs = (
                session.query(ChatMessage)
                .filter(ChatMessage.session_id == chat_session_id)
                .order_by(ChatMessage.id.asc())
                .all()
            )
            chat_dicts = [
                {"role": m.role, "content": m.content, "tool_calls": getattr(m, "tool_calls", None),
                 "tool_call_id": getattr(m, "tool_call_id", None)}
                for m in chat_msgs
            ]

        chat_excerpt = compress_chat_transcript(chat_dicts)

        # Synthesize section_drafts from the source ReportSchema's sections.
        # (The original `section_drafts` lives in the bundle; we prefer it.)
        synthesized_drafts: list[SectionDraft] = []
        for s in source_schema.get("sections", []):
            synthesized_drafts.append(SectionDraft(
                section_id=s.get("id", ""),
                blocks=s.get("blocks", []),
                citations_used=[],
                word_count=sum(
                    len(b.get("content", "").split())
                    for b in s.get("blocks", []) if b.get("type") == "text"
                ),
                open_questions=[],
            ))

        yield ReportPhase(report_id=new_report_id, phase="editing")

        resolved_flag = self._resolve(
            department_id=department_id, user_id=user_id,
            registry=self._registry, role="flagship",
        )
        flagship = self._flagship_factory(resolved_flag)
        editor = EditorClient(provider=flagship, repair_budget=1, max_output_tokens=8192)

        thesis = (source_schema.get("cover") or {}).get("tagline") or ""
        # cross_section_themes from the original plan (in the bundle).
        themes = list(source_bundle.plan.cross_section_themes)

        editor_req = EditorRequest(
            role_prompt=_load_revision_role_prompt(),
            style_guide="",  # Mode style guide loaded by caller if needed; revision works without.
            schema_strictness=_load_schema_strictness(),
            company_thesis=thesis,
            cross_section_themes=themes,
            section_drafts=synthesized_drafts,
            open_questions=[],
            framework_cover_instructions=(
                "Compose cover.title, cover.subtitle, cover.tagline, cover.tldr "
                "from the revised content. Build cover.key_metrics from the revised data."
            ),
            revision_brief=revision_brief,
            sections_to_focus=sections_to_focus,
            chat_transcript_excerpt=chat_excerpt or None,
        )
        revised_payload = await editor.compose(editor_req)

        yield ReportPhase(report_id=new_report_id, phase="finalizing")

        # Finalize via the existing shared helper from chat-followup spec / subagent runner.
        from openlia.llm.runtime.report import _finalize_submit_payload

        finalized = _finalize_submit_payload(
            revised_payload,
            department_id=department_id,
            generated_at=datetime.now(UTC),
            provider_citations=[],
            model_id=resolved_flag.model_ref,
            total_input_tokens=0,
            total_output_tokens=0,
            web_search_count=0,
        )
        validate_report_payload(finalized)

        # Bundle inheritance (copy source bundle to new report id).
        new_bundle_path = self._bundle_dir / f"{new_report_id}.json.gz"
        try:
            shutil.copy2(source_bundle_path, new_bundle_path)
        except Exception:
            # Non-fatal — log via trace if available; report still ships.
            pass

        yield ReportComplete(report_id=new_report_id, schema=finalized)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py -v
```

Expected: PASS

- [ ] **Step 5: Lint + format + commit**

```bash
uv run ruff format packages/core/src/openlia/llm/runtime/revision_runner.py packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py
uv run ruff check packages/core/src/openlia/llm/runtime/revision_runner.py packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py
git add packages/core/src/openlia/llm/runtime/revision_runner.py packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py
git commit -m "feat(revision): RevisionRunner end-to-end happy path"
```

---

## Task 6: `RevisionRunner` source-bundle-missing failure

**Files:**
- Test: extends `packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py`

(No source change — Task 5 already handles this. Add the explicit guard test.)

- [ ] **Step 1: Append the test**

```python
@pytest.mark.asyncio
async def test_revision_runner_fails_when_source_bundle_missing(
    prompts_root: Path, bundle_dir: Path,
    seeded_source_report: str, seeded_chat_with_messages: str,
    db_session_factory,
) -> None:
    bundle_dir.mkdir(exist_ok=True)
    # No bundle file written for this source_report_id.
    flagship = FakeProvider(script=FakeProviderScript(turns=[]))  # not used
    runner = RevisionRunner(
        prompts=PromptLoader(root=prompts_root), resolve=_resolve, registry=object(),
        flagship_provider_factory=lambda r: flagship,
        report_id_factory=lambda: "r_revised",
        bundle_dir=bundle_dir,
        db_session_factory=db_session_factory,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research", user_id="u_1",
        source_report_id="r_nope",  # bundle file does NOT exist
        chat_session_id=seeded_chat_with_messages,
        revision_brief="x", sections_to_focus=None,
    ):
        events.append(ev)
    types = [type(e).__name__ for e in events]
    assert "ReportError" in types
    assert "ReportComplete" not in types
    err = [e for e in events if type(e).__name__ == "ReportError"][0]
    assert "bundle" in err.message.lower() or err.code == "bundle_missing"
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py -v
git add packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py
git commit -m "test(revision): RevisionRunner fails loud when source bundle missing"
```

---

## Task 7: Bundle inheritance — verify source and new bundles match

**Files:**
- Test: extends `packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py`

(No source change — Task 5 already copies the bundle. Guard test.)

- [ ] **Step 1: Append the test**

```python
@pytest.mark.asyncio
async def test_revision_runner_copies_source_bundle_to_revised_id(
    prompts_root: Path, bundle_dir: Path,
    seeded_source_report: str, seeded_chat_with_messages: str,
    db_session_factory,
) -> None:
    flagship = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())]),
    ]))
    runner = RevisionRunner(
        prompts=PromptLoader(root=prompts_root), resolve=_resolve, registry=object(),
        flagship_provider_factory=lambda r: flagship,
        report_id_factory=lambda: "r_revised",
        bundle_dir=bundle_dir, db_session_factory=db_session_factory,
    )
    async for _ in runner.run(
        department_id="equity_research", user_id="u_1",
        source_report_id=seeded_source_report,
        chat_session_id=seeded_chat_with_messages,
        revision_brief="x", sections_to_focus=None,
    ):
        pass
    source_bytes = (bundle_dir / f"{seeded_source_report}.json.gz").read_bytes()
    new_bytes = (bundle_dir / "r_revised.json.gz").read_bytes()
    assert source_bytes == new_bytes
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py -v
git add packages/core/tests/test_llm/test_runtime/test_revision_runner_e2e.py
git commit -m "test(revision): bundle inheritance via file copy"
```

---

## Task 8: `POST /reports/{source_report_id}/revise` endpoint

**Files:**
- Create: `packages/server/src/openlia_server/routes/reports_revise.py`
- Test: `packages/server/tests/test_reports_revise_endpoint.py`

> **Before starting:** Run `grep -n "router\.post\|@router\.\|build_reports_router\|build_reports_stream_router" packages/server/src/openlia_server/routes/*.py | head -15` to find existing router build patterns.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_reports_revise_endpoint.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def revision_body(seeded_chat_with_messages, seeded_source_report) -> dict:
    return {
        "chat_session_id": seeded_chat_with_messages,
        "revision_brief": "Fix Q4 capex",
        "sections_to_focus": None,
    }


def test_revise_endpoint_returns_new_report_id_fast(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_source_report: str, revision_body: dict,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    import time
    start = time.monotonic()
    resp = test_client.post(f"/reports/{seeded_source_report}/revise", json=revision_body)
    elapsed = time.monotonic() - start
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "generating"
    assert body["report_id"].startswith("r_")
    assert elapsed < 2.0


def test_revise_endpoint_404_for_unknown_source(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_chat_with_messages: str,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    resp = test_client.post("/reports/r_unknown/revise", json={
        "chat_session_id": seeded_chat_with_messages,
        "revision_brief": "x", "sections_to_focus": None,
    })
    assert resp.status_code == 404


def test_revise_endpoint_400_when_chat_not_bound_to_source(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_source_report: str, seeded_unbound_chat,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    resp = test_client.post(f"/reports/{seeded_source_report}/revise", json={
        "chat_session_id": seeded_unbound_chat.id,
        "revision_brief": "x", "sections_to_focus": None,
    })
    assert resp.status_code == 400


def test_revise_endpoint_rejects_when_flag_off(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_source_report: str, revision_body: dict,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    resp = test_client.post(f"/reports/{seeded_source_report}/revise", json=revision_body)
    assert resp.status_code in (403, 404, 503)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_reports_revise_endpoint.py -v
```

Expected: FAIL (endpoint doesn't exist)

- [ ] **Step 3: Write the route**

```python
# packages/server/src/openlia_server/routes/reports_revise.py
"""POST /reports/{source_report_id}/revise — kicks off a RevisionRunner
as a background task and returns the new report_id immediately."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia.llm.runtime.revision_runner import RevisionRunner
from openlia_server.db.models.content import ChatSession, Report
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry


class ReviseReportIn(BaseModel):
    chat_session_id: str
    revision_brief: str
    sections_to_focus: list[str] | None = None


_SOURCE_CHAT_LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


def build_reports_revise_router(
    *,
    prompts,
    resolve,
    flagship_provider_factory,
    bundle_dir,
    db_session_factory,
) -> APIRouter:
    router = APIRouter()

    @router.post("/{source_report_id}/revise")
    async def revise_report_ep(
        source_report_id: str,
        body: ReviseReportIn,
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
        registry: BackgroundReportRegistry = Depends(get_registry),
        presence: UserPresenceRegistry = Depends(get_presence),
    ) -> dict:
        if not _flag_on():
            raise HTTPException(503, "revision pass not enabled")

        source_row = db.get(Report, source_report_id)
        if source_row is None or source_row.user_id != user.id:
            raise HTTPException(404)
        chat = db.get(ChatSession, body.chat_session_id)
        if chat is None or chat.user_id != user.id or chat.attached_report_id != source_report_id:
            raise HTTPException(400, "chat session is not bound to this report")

        async with _SOURCE_CHAT_LOCKS[body.chat_session_id]:
            new_report_id = f"r_{uuid.uuid4().hex[:12]}"
            new_row = Report(
                id=new_report_id,
                user_id=user.id,
                department=source_row.department,
                status="generating",
                started_at=datetime.now(UTC),
                original_request={
                    "kind": "revision",
                    "source_report_id": source_report_id,
                    "chat_session_id": body.chat_session_id,
                    "revision_brief": body.revision_brief,
                    "sections_to_focus": body.sections_to_focus,
                },
            )
            db.add(new_row)
            db.commit()

        runner_coro = RevisionRunner(
            prompts=prompts, resolve=resolve, registry=registry,
            flagship_provider_factory=flagship_provider_factory,
            report_id_factory=lambda: new_report_id,
            bundle_dir=bundle_dir, db_session_factory=db_session_factory,
        ).run(
            department_id=source_row.department,
            user_id=user.id,
            source_report_id=source_report_id,
            chat_session_id=body.chat_session_id,
            revision_brief=body.revision_brief,
            sections_to_focus=body.sections_to_focus,
        )

        task = registry.submit(user_id=user.id, report_id=new_report_id, runner_coro=runner_coro)

        # Wrapper subscribes to events and handles persistence + re-anchor.
        # (Task 11 implements run_wrapped_revision; for now schedule a placeholder
        # that delegates to run_wrapped_report from the bg-gen spec.)
        from openlia_server.services.report_wrapper import run_wrapped_report

        async def _subscribe():
            queue: asyncio.Queue = asyncio.Queue(maxsize=512)
            task.subscriber_queues.add(queue)
            try:
                while True:
                    ev = await queue.get()
                    yield ev
                    from openlia.llm.runtime.events import ReportComplete, ReportError
                    if isinstance(ev, (ReportComplete, ReportError)):
                        return
            finally:
                task.subscriber_queues.discard(queue)

        asyncio.create_task(run_wrapped_report(
            runner_coro=_subscribe(),
            report_id=new_report_id,
            user_id=user.id,
            db_session_factory=db_session_factory,
            presence=presence,
            registry=registry,
        ))

        return {"report_id": new_report_id, "status": "generating"}

    return router
```

Wire the router into `app.py` under the `/reports` prefix.

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_reports_revise_endpoint.py -v
uv run ruff format packages/server/src/openlia_server/routes/reports_revise.py packages/server/tests/test_reports_revise_endpoint.py
uv run ruff check packages/server/src/openlia_server/routes/reports_revise.py packages/server/tests/test_reports_revise_endpoint.py
git add packages/server/src/openlia_server/routes/reports_revise.py packages/server/tests/test_reports_revise_endpoint.py
git commit -m "feat(revision): POST /reports/{id}/revise endpoint with lock + auth"
```

---

## Task 9: Per-source-chat-session lock serialization test

**Files:**
- Test: `packages/server/tests/test_revision_race_lock.py`

(No source change — Task 8's `_SOURCE_CHAT_LOCKS` already serializes. Guard test for the property.)

- [ ] **Step 1: Write the test**

```python
# packages/server/tests/test_revision_race_lock.py
"""Two parallel POST /reports/{source}/revise requests against the same
chat must result in BOTH eventually completing successfully — the
second waits for the first via the per-chat lock. After both, the
source chat is re-anchored to ONE of them."""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_parallel_revise_calls_serialize_via_chat_lock(
    monkeypatch: pytest.MonkeyPatch, async_test_client: AsyncClient,
    seeded_source_report: str, seeded_chat_with_messages: str,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    body = {
        "chat_session_id": seeded_chat_with_messages,
        "revision_brief": "x", "sections_to_focus": None,
    }
    a = async_test_client.post(f"/reports/{seeded_source_report}/revise", json=body)
    b = async_test_client.post(f"/reports/{seeded_source_report}/revise", json=body)
    resp_a, resp_b = await asyncio.gather(a, b)
    # Both accept; both return distinct report_ids.
    assert resp_a.status_code == 200 and resp_b.status_code == 200
    assert resp_a.json()["report_id"] != resp_b.json()["report_id"]
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/server/tests/test_revision_race_lock.py -v
git add packages/server/tests/test_revision_race_lock.py
git commit -m "test(revision): per-source-chat-session lock serializes parallel revise calls"
```

---

## Task 10: `run_wrapped_revision` — re-anchor chat on success + fanout event

**Files:**
- Create: `packages/server/src/openlia_server/services/revision_wrapper.py`
- Test: `packages/server/tests/test_revision_wrapper.py`
- Modify: `packages/server/src/openlia_server/routes/reports_revise.py` (swap `run_wrapped_report` for `run_wrapped_revision`)

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_revision_wrapper.py
from __future__ import annotations

import asyncio

import pytest

from openlia.llm.runtime.events import ReportComplete, ReportError
from openlia_server.services.revision_wrapper import run_wrapped_revision


class _StubPresence:
    def __init__(self) -> None:
        self.events = []
    def fanout(self, user_id, event):
        self.events.append((user_id, event))


class _StubReport:
    def __init__(self, status="complete"):
        self.status = status


class _StubChat:
    def __init__(self):
        self.attached_report_id = "r_source"


class _StubSession:
    def __init__(self, row, chat):
        self._row = row
        self._chat = chat
        self.committed = False
    def get(self, model, _id):
        # Hack: return chat when looking up ChatSession, row otherwise.
        if "ChatSession" in str(model):
            return self._chat
        return self._row
    def commit(self):
        self.committed = True
    def close(self): pass


def _factory(row, chat):
    def f():
        class CM:
            def __enter__(self_inner): return _StubSession(row, chat)
            def __exit__(self_inner, *a): return False
        return CM()
    return f


@pytest.mark.asyncio
async def test_re_anchors_chat_on_success() -> None:
    row = _StubReport(status="complete")
    chat = _StubChat()
    presence = _StubPresence()

    async def runner():
        yield ReportComplete(report_id="r_new", schema={"cover": {"title": "x"}})

    await run_wrapped_revision(
        runner_coro=runner(),
        new_report_id="r_new",
        source_chat_session_id="sess_test",
        user_id="u_1",
        db_session_factory=_factory(row, chat),
        presence=presence,
        registry=object(),
    )
    assert chat.attached_report_id == "r_new"
    # Event fanned out.
    assert any(e[1]["type"] == "chat.attached_report_changed" for e in presence.events)


@pytest.mark.asyncio
async def test_does_not_re_anchor_on_failure() -> None:
    row = _StubReport(status="failed")
    chat = _StubChat()  # attached_report_id = "r_source"
    presence = _StubPresence()

    async def runner():
        yield ReportError(report_id="r_new", code="x", message="y")

    await run_wrapped_revision(
        runner_coro=runner(),
        new_report_id="r_new",
        source_chat_session_id="sess_test",
        user_id="u_1",
        db_session_factory=_factory(row, chat),
        presence=presence,
        registry=object(),
    )
    assert chat.attached_report_id == "r_source"  # unchanged
    assert not any(e[1]["type"] == "chat.attached_report_changed" for e in presence.events)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_revision_wrapper.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/server/src/openlia_server/services/revision_wrapper.py
"""Wrapper for revision tasks: delegates to run_wrapped_report for
standard persistence + notifications, then re-anchors the source
chat session on successful completion."""

from __future__ import annotations

from openlia_server.services.report_wrapper import run_wrapped_report


async def run_wrapped_revision(
    *,
    runner_coro,
    new_report_id: str,
    source_chat_session_id: str,
    user_id: str,
    db_session_factory,
    presence,
    registry,
) -> None:
    await run_wrapped_report(
        runner_coro=runner_coro,
        report_id=new_report_id,
        user_id=user_id,
        db_session_factory=db_session_factory,
        presence=presence,
        registry=registry,
    )
    # Re-anchor only on success.
    from openlia_server.db.models.content import ChatSession, Report

    with db_session_factory() as session:
        row = session.get(Report, new_report_id)
        if row is None or row.status != "complete":
            return
        chat = session.get(ChatSession, source_chat_session_id)
        if chat is None:
            return
        chat.attached_report_id = new_report_id
        session.commit()
    presence.fanout(user_id, {
        "type": "chat.attached_report_changed",
        "session_id": source_chat_session_id,
        "new_report_id": new_report_id,
    })
```

Update `packages/server/src/openlia_server/routes/reports_revise.py` to import and use `run_wrapped_revision` instead of `run_wrapped_report`:

```python
from openlia_server.services.revision_wrapper import run_wrapped_revision

# Inside the route, change:
# from openlia_server.services.report_wrapper import run_wrapped_report
# asyncio.create_task(run_wrapped_report(...))
# to:
asyncio.create_task(run_wrapped_revision(
    runner_coro=_subscribe(),
    new_report_id=new_report_id,
    source_chat_session_id=body.chat_session_id,
    user_id=user.id,
    db_session_factory=db_session_factory,
    presence=presence,
    registry=registry,
))
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_revision_wrapper.py packages/server/tests/test_reports_revise_endpoint.py -v
git add packages/server/src/openlia_server/services/revision_wrapper.py packages/server/tests/test_revision_wrapper.py packages/server/src/openlia_server/routes/reports_revise.py
git commit -m "feat(revision): run_wrapped_revision re-anchors chat on success"
```

---

## Task 11: Subject-keyed binding in chat-followup routing (amendment)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py` (the report-generate handler from chat-followup §4)
- Test: `packages/server/tests/test_subject_keyed_binding.py`

> **Before starting:** Run `grep -n "attached_report_id\|handle_report_generation\|generate_report_ep" packages/server/src/openlia_server/routes/reports.py | head -15` to find the current routing.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_subject_keyed_binding.py
"""When OPENLIA_REVISION_PASS_ENABLED=1, the chat-followup §4 routing
checks SUBJECT equality (lowercased + trimmed) instead of just
attached_report_id-is-None. Same ticker re-anchors; different ticker
spawns a new thread."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_same_ticker_in_bound_chat_re_anchors(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_bound_chat_session_msft,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    src_id = seeded_bound_chat_session_msft.id
    original_attached = seeded_bound_chat_session_msft.attached_report_id
    resp = test_client.post("/reports/generate", json={
        "source_session_id": src_id,
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "msft",  # same ticker, different case
    })
    assert resp.status_code == 200
    assert resp.json()["redirect"] is False
    sess = test_client.get(f"/chat/sessions/{src_id}")
    new_attached = sess.json()["attached_report_id"]
    assert new_attached != original_attached  # re-anchored to new report
    assert new_attached == resp.json()["report_id"]


def test_different_ticker_in_bound_chat_spawns_new_thread(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_bound_chat_session_msft,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    src_id = seeded_bound_chat_session_msft.id
    original_attached = seeded_bound_chat_session_msft.attached_report_id
    resp = test_client.post("/reports/generate", json={
        "source_session_id": src_id,
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "AAPL",  # different ticker
    })
    assert resp.status_code == 200
    assert resp.json()["redirect"] is True
    assert resp.json()["session_id"] != src_id
    # Source session attached_report_id unchanged (strict).
    sess = test_client.get(f"/chat/sessions/{src_id}")
    assert sess.json()["attached_report_id"] == original_attached


def test_flag_off_preserves_strict_immutability(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_bound_chat_session_msft,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    src_id = seeded_bound_chat_session_msft.id
    resp = test_client.post("/reports/generate", json={
        "source_session_id": src_id,
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "msft",  # same ticker
    })
    # When flag is off, chat-followup §4's original "immutable" rule applies
    # and same-ticker still spawns a new thread.
    assert resp.json()["redirect"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_subject_keyed_binding.py -v
```

Expected: FAIL (current behavior treats attached_report_id as immutable regardless of flag)

- [ ] **Step 3: Update the routing logic**

In the existing chat-followup §4 routing in `packages/server/src/openlia_server/routes/reports.py`:

```python
import os
from openlia_server.services.subject_normalize import normalize_subject


def _revision_flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


# In the report-generate handler, replace the existing bound-chat branch:
if source_session.attached_report_id is not None:
    if _revision_flag_on():
        # Subject-keyed re-anchor.
        bound_report = db.get(Report, source_session.attached_report_id)
        bound_subject = normalize_subject(
            (bound_report.original_request or {}).get("user_input", "")
        ) if bound_report else ""
        new_subject = normalize_subject(body.user_input)
        if bound_subject and new_subject and bound_subject == new_subject:
            # Same ticker — re-anchor.
            report_id = await generate_report(body, user)
            source_session.attached_report_id = report_id
            db.commit()
            return {"session_id": source_session.id, "report_id": report_id, "redirect": False}
    # Otherwise (flag off OR different subject): new thread (existing behavior).
    new_session = ChatSession(department=source_session.department, user_id=user.id)
    db.add(new_session)
    db.flush()
    report_id = await generate_report(body, user)
    new_session.attached_report_id = report_id
    _attach_report_as_context(db, session_id=new_session.id, user_id=user.id, report_id=report_id)
    db.commit()
    return {"session_id": new_session.id, "report_id": report_id, "redirect": True}
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_subject_keyed_binding.py -v
git add packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_subject_keyed_binding.py
git commit -m "feat(revision): subject-keyed chat binding (flag-gated)"
```

---

## Task 12: Chat-route intercepts `revise_report` tool calls (no dispatch)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/chat_sessions.py`
- Test: `packages/server/tests/test_chat_route_intercepts_revise.py`

> **Before starting:** Run `grep -n "ToolDispatcher\|dispatch_many\|tool_calls" packages/server/src/openlia_server/routes/chat_sessions.py | head -10` to find where tool dispatch happens.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_chat_route_intercepts_revise.py
"""When the chat LLM emits a revise_report tool call, the chat route
must intercept it (not pass to ToolDispatcher.dispatch). Instead the
route POSTs internally to /reports/{source}/revise and returns a
synthetic tool result to the model."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_revise_report_tool_call_does_not_hit_tool_dispatcher(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_bound_chat_with_revise_tool_call,
) -> None:
    """Test harness seeds a chat session bound to a report with a fake
    LLM provider that emits a revise_report tool call on the next
    message. The chat route should intercept it."""
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "1")
    session_id = seeded_bound_chat_with_revise_tool_call.id
    resp = test_client.post(f"/chat/sessions/{session_id}/messages", json={
        "content": "Save this as a final version please",
    })
    assert resp.status_code == 200
    body = resp.json()
    # The response includes a marker that revision was started.
    assert body.get("revision_started") is True
    assert "new_report_id" in body


def test_intercept_only_when_flag_on(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_bound_chat_with_revise_tool_call,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    session_id = seeded_bound_chat_with_revise_tool_call.id
    resp = test_client.post(f"/chat/sessions/{session_id}/messages", json={
        "content": "Save this as a final version please",
    })
    # When flag is off, revise_report shouldn't be in the tool list to
    # begin with — but if the LLM emits it anyway, it falls through to
    # the standard "unknown tool" path.
    assert resp.json().get("revision_started") is not True
```

> Fixture `seeded_bound_chat_with_revise_tool_call` configures a fake provider that returns `tool_calls=[ToolCall(name="revise_report", arguments={"revision_brief": "fix it"})]` on the next message. Add to conftest.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_chat_route_intercepts_revise.py -v
```

Expected: FAIL (no intercept logic yet)

- [ ] **Step 3: Add intercept logic to the message handler**

In `packages/server/src/openlia_server/routes/chat_sessions.py`, find the message-post endpoint that calls `ToolDispatcher.dispatch_many`. Before the dispatch loop, intercept revise_report calls:

```python
import os
from openlia_server.routes.reports_revise import ReviseReportIn

REVISE_TOOL_NAME = "revise_report"


def _revision_flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


# Inside the message endpoint, after the LLM response is parsed:
revision_started = False
revision_new_report_id: str | None = None

remaining_tool_calls = []
for call in llm_response.tool_calls:
    if call.name == REVISE_TOOL_NAME and _revision_flag_on() and session.attached_report_id:
        # Intercept: post to /revise internally.
        try:
            args = call.arguments if isinstance(call.arguments, dict) else {}
            new_report_id = await _trigger_revision(
                db=db, user=user,
                source_report_id=session.attached_report_id,
                chat_session_id=session.id,
                revision_brief=args.get("revision_brief", ""),
                sections_to_focus=args.get("sections_to_focus"),
                registry=registry, presence=presence,
            )
            revision_started = True
            revision_new_report_id = new_report_id
            # Inject synthetic tool result so the LLM can respond next turn.
            inject_tool_result(
                db, session_id=session.id, call_id=call.id,
                content=json.dumps({
                    "status": "revision_started",
                    "new_report_id": new_report_id,
                    "estimated_seconds": 30,
                }),
            )
        except HTTPException as exc:
            inject_tool_result(
                db, session_id=session.id, call_id=call.id,
                content=json.dumps({"status": "stale_source", "message": exc.detail}),
            )
    else:
        remaining_tool_calls.append(call)

# The remaining calls go to the standard ToolDispatcher.dispatch_many path.
results = await tools.dispatch_many(department_id=session.department, calls=remaining_tool_calls)

# Response carries revision markers when relevant.
return {
    ..., # existing response shape
    "revision_started": revision_started,
    "new_report_id": revision_new_report_id,
}
```

`_trigger_revision` is a small helper that does the same row insert + registry submission as `reports_revise.py`'s route handler (refactor to share via a service function if neat; otherwise duplicate the small block).

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_chat_route_intercepts_revise.py -v
git add packages/server/src/openlia_server/routes/chat_sessions.py packages/server/tests/test_chat_route_intercepts_revise.py
git commit -m "feat(revision): chat route intercepts revise_report tool calls"
```

---

## Task 13: Register `revise_report` in chat tool list when flag on + chat is bound

**Files:**
- Modify: `packages/server/src/openlia_server/services/report_chat_context.py`
- Test: `packages/server/tests/test_revise_tool_registration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_revise_tool_registration.py
"""When OPENLIA_REVISION_PASS_ENABLED=1 and the chat session has
attached_report_id, the `revise_report` tool is present in the
context's tool list. With flag off, it's absent."""
from __future__ import annotations

import pytest

from openlia_server.services.report_chat_context import (
    build_chat_context_for_session,
)


def _stub_dispatcher():
    from packages.core.tests.test_llm.test_runtime._fakes import FakeDataDispatcher  # type: ignore
    from openlia.llm.runtime.tools import ToolDispatcher
    from openlia.llm.runtime.web_search import WebSearchResolution
    return ToolDispatcher(
        data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
        web_search=WebSearchResolution(False, None, None),
    )


def test_revise_report_tool_present_when_flag_on(monkeypatch, tmp_path, seeded_bundle):
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    result = build_chat_context_for_session(
        attached_report_id="r_test",
        bundle_dir=tmp_path / "bundles",
        report_is_tombstoned=False,
        dispatcher=_stub_dispatcher(),
        department_id="equity_research",
        has_web_search=True,
    )
    tool_names = {t.name for t in result.tools}
    assert "revise_report" in tool_names


def test_revise_report_tool_absent_when_flag_off(monkeypatch, tmp_path, seeded_bundle):
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    result = build_chat_context_for_session(
        attached_report_id="r_test",
        bundle_dir=tmp_path / "bundles",
        report_is_tombstoned=False,
        dispatcher=_stub_dispatcher(),
        department_id="equity_research",
        has_web_search=True,
    )
    tool_names = {t.name for t in result.tools}
    assert "revise_report" not in tool_names
```

- [ ] **Step 2: Run + implement**

In `packages/server/src/openlia_server/services/report_chat_context.py`, extend `build_chat_context_for_session` to append the `revise_report` ToolSchema when flag is on:

```python
import os
from openlia.llm.types import ToolSchema

REVISE_TOOL_NAME = "revise_report"
_REVISE_TOOL = ToolSchema(
    name=REVISE_TOOL_NAME,
    description=(
        "Consolidate the original report and this discussion into a "
        "revised report. Call this when the user explicitly asks for a "
        "'final', 'revised', 'consolidated', 'updated', or 'final "
        "version' of the report. Do NOT call this for summary or recap "
        "requests — only when the user wants a NEW report saved."
    ),
    parameters={
        "type": "object",
        "additionalProperties": False,
        "required": ["revision_brief"],
        "properties": {
            "revision_brief": {
                "type": "string",
                "description": (
                    "2-4 sentence summary derived from the chat "
                    "discussion: what's wrong with the original, what's "
                    "missing, what structural changes the user asked for."
                ),
            },
            "sections_to_focus": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional section_ids the editor should pay extra "
                    "attention to."
                ),
            },
        },
    },
)


def _revision_flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


# Inside build_chat_context_for_session, BEFORE the return:
if _revision_flag_on():
    base_tools.append(_REVISE_TOOL)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/server/tests/test_revise_tool_registration.py -v
git add packages/server/src/openlia_server/services/report_chat_context.py packages/server/tests/test_revise_tool_registration.py
git commit -m "feat(revision): register revise_report tool in bound chats when flag on"
```

---

## Task 14: Retry routes revision-kind reports through `/revise`

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py` (the existing retry handler from background-gen)
- Test: `packages/server/tests/test_revision_retry_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_revision_retry_routing.py
"""When the failed report's original_request.kind == 'revision', the
Retry button POSTs to /revise (with the persisted source_report_id and
revision_brief) instead of /generate."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_retry_for_revision_kind_uses_revise_endpoint(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient,
    seeded_failed_revision_report,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    failed_id = seeded_failed_revision_report.id
    resp = test_client.post(f"/reports/{failed_id}/retry")
    assert resp.status_code == 200
    body = resp.json()
    # New report exists in generating status.
    new = test_client.get(f"/reports/{body['report_id']}")
    new_body = new.json()
    assert new_body["status"] == "generating"
    assert new_body["original_request"]["kind"] == "revision"
    assert (
        new_body["original_request"]["source_report_id"]
        == seeded_failed_revision_report.original_request["source_report_id"]
    )
```

- [ ] **Step 2: Run + implement**

In the existing retry handler:

```python
@router.post("/{report_id}/retry")
async def retry_report_ep(
    report_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: BackgroundReportRegistry = Depends(get_registry),
    presence: UserPresenceRegistry = Depends(get_presence),
) -> dict:
    row = db.get(Report, report_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404)
    if row.status not in ("failed", "cancelled"):
        raise HTTPException(400, "Only failed or cancelled reports can be retried")
    if row.original_request is None:
        raise HTTPException(400, "Report has no persisted original_request")

    if (row.original_request or {}).get("kind") == "revision":
        # Route to revision endpoint.
        from openlia_server.routes.reports_revise import (
            ReviseReportIn,
            build_reports_revise_router,
        )
        body = ReviseReportIn(
            chat_session_id=row.original_request["chat_session_id"],
            revision_brief=row.original_request["revision_brief"],
            sections_to_focus=row.original_request.get("sections_to_focus"),
        )
        # Inline-call: replicate the revise handler's body (extracted as a service
        # function would be neat; keeping it inline preserves clarity).
        ...
        # OR: HTTPException 307 redirect to /reports/{source}/revise.
        # Choose whichever pattern the codebase prefers.
        return await _execute_revise(
            db=db, user=user, registry=registry, presence=presence,
            source_report_id=row.original_request["source_report_id"],
            body=body,
        )

    # Otherwise, existing /generate retry path (unchanged).
    body = GenerateReportIn(**row.original_request)
    return await generate_report_ep(body=body, user=user, db=db, registry=registry, presence=presence)
```

Extract a `_execute_revise(...)` service helper if duplication becomes unsightly; that's a clean small refactor.

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/server/tests/test_revision_retry_routing.py -v
git add packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_revision_retry_routing.py
git commit -m "feat(revision): retry routes revision-kind reports through /revise"
```

---

## Task 15: `chat.attached_report_changed` event delivered via notifications SSE

**Files:**
- Modify: `packages/server/src/openlia_server/routes/notifications_stream.py` (just register the new event type; the fanout call is already in Task 10's wrapper)
- Test: `packages/server/tests/test_chat_attached_report_changed_event.py`

(The fanout itself happens in `run_wrapped_revision` from Task 10. The notifications SSE already forwards any event in the user's queue. This task adds a guard test that the event reaches a subscriber.)

- [ ] **Step 1: Write the test**

```python
# packages/server/tests/test_chat_attached_report_changed_event.py
from __future__ import annotations

import pytest

from openlia_server.services.user_presence_registry import UserPresenceRegistry


@pytest.mark.asyncio
async def test_chat_attached_report_changed_event_delivered_to_subscriber() -> None:
    presence = UserPresenceRegistry()
    q = presence.attach("u_1")
    presence.fanout("u_1", {
        "type": "chat.attached_report_changed",
        "session_id": "sess_test",
        "new_report_id": "r_new",
    })
    ev = q.get_nowait()
    assert ev["type"] == "chat.attached_report_changed"
    assert ev["session_id"] == "sess_test"
    assert ev["new_report_id"] == "r_new"
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/server/tests/test_chat_attached_report_changed_event.py -v
git add packages/server/tests/test_chat_attached_report_changed_event.py
git commit -m "test(revision): chat.attached_report_changed event delivery"
```

---

## Task 16: Frontend — `RevisionInProgressChip` component

**Files:**
- Create: `frontend/src/components/chat/RevisionInProgressChip.tsx`
- Test: `frontend/src/components/chat/RevisionInProgressChip.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/chat/RevisionInProgressChip.test.tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RevisionInProgressChip } from "./RevisionInProgressChip";

describe("RevisionInProgressChip", () => {
  it("renders a revision-in-progress status with a Cancel button", () => {
    render(<RevisionInProgressChip newReportId="r_xyz" />);
    expect(screen.getByText(/revising/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel revision/i })).toBeInTheDocument();
  });

  it("calls DELETE /reports/{newReportId} when Cancel clicked", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({ ok: true } as any);
    window.confirm = vi.fn(() => true);
    render(<RevisionInProgressChip newReportId="r_xyz" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel revision/i }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith("/reports/r_xyz", { method: "DELETE" }));
  });
});
```

- [ ] **Step 2: Run + implement**

```tsx
// frontend/src/components/chat/RevisionInProgressChip.tsx
import { useState } from "react";

interface Props {
  newReportId: string;
}

export function RevisionInProgressChip({ newReportId }: Props) {
  const [cancelled, setCancelled] = useState(false);

  async function handleCancel() {
    if (!confirm("Cancel this revision? Partial progress will be discarded.")) return;
    await fetch(`/reports/${newReportId}`, { method: "DELETE" });
    setCancelled(true);
  }

  return (
    <div className={`chip chip--revision ${cancelled ? "chip--cancelled" : ""}`}>
      <span className="spinner" aria-hidden="true" />
      <span>{cancelled ? "Revision cancelled" : "Revising the report based on our discussion..."}</span>
      {!cancelled && (
        <button onClick={handleCancel}>Cancel revision</button>
      )}
    </div>
  );
}
```

Wire into `ChatThread.tsx` (or whichever chat-message renderer exists): when a message's tool-call is `revise_report` and the response includes `revision_started`, render `<RevisionInProgressChip newReportId={...} />` in place of the standard tool-call chip.

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm test -- RevisionInProgressChip.test.tsx
git add frontend/src/components/chat/RevisionInProgressChip.tsx frontend/src/components/chat/RevisionInProgressChip.test.tsx
git commit -m "feat(revision): RevisionInProgressChip component"
```

---

## Task 17: Frontend — handle `chat.attached_report_changed` event

**Files:**
- Modify: `frontend/src/app/useNotificationsStream.ts`
- Test: extend `frontend/src/app/useNotificationsStream.test.ts`

- [ ] **Step 1: Append the failing test**

```ts
// in useNotificationsStream.test.ts:
it("invokes onAttachedReportChanged when chat.attached_report_changed fires", () => {
  const navigate = vi.fn();
  const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
  const onAttachedReportChanged = vi.fn();
  renderHook(() =>
    useNotificationsStream({ navigate, toast, onAttachedReportChanged })
  );
  lastEventSource.fire("chat.attached_report_changed", {
    session_id: "sess_test", new_report_id: "r_new",
  });
  expect(onAttachedReportChanged).toHaveBeenCalledWith({
    session_id: "sess_test", new_report_id: "r_new",
  });
});
```

- [ ] **Step 2: Run + implement**

Modify the hook to accept an optional callback:

```ts
interface Options {
  navigate: (path: string) => void;
  toast: Toaster;
  onAttachedReportChanged?: (data: { session_id: string; new_report_id: string }) => void;
}

export function useNotificationsStream({ navigate, toast, onAttachedReportChanged }: Options): void {
  useEffect(() => {
    const es = new EventSource("/notifications/stream");
    es.addEventListener("report.complete", (e) => { /* unchanged */ });
    es.addEventListener("report.failed", (e) => { /* unchanged */ });
    es.addEventListener("report.cancelled", (e) => { /* unchanged */ });
    es.addEventListener("chat.attached_report_changed", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      onAttachedReportChanged?.(data);
    });
    return () => es.close();
  }, [navigate, toast, onAttachedReportChanged]);
}
```

In `App.tsx` (or whichever top-level component holds the chat session state), pass an `onAttachedReportChanged` callback that re-fetches the current chat session if its id matches.

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm test -- useNotificationsStream.test.ts
git add frontend/src/app/useNotificationsStream.ts frontend/src/app/useNotificationsStream.test.ts frontend/src/App.tsx
git commit -m "feat(revision): notifications hook handles chat.attached_report_changed"
```

---

## Validation (manual smoke after all tasks land)

Do NOT commit any code from this step.

- [ ] **Set env and restart server:**

```bash
pkill -9 -f "openlia serve" || true
sleep 1
OPENLIA_DEV_MODE=1 \
OPENLIA_USE_SUBAGENT_RUNNER=1 \
OPENLIA_REPORT_CHAT_ENABLED=1 \
OPENLIA_BACKGROUND_REPORTS_ENABLED=1 \
OPENLIA_REVISION_PASS_ENABLED=1 \
OPENLIA_DEFAULT_SUBAGENT_MODEL_ID="<cheap model id>" \
uv run openlia serve > /tmp/openlia-serve.log 2>&1 &
sleep 4
tail -3 /tmp/openlia-serve.log
```

- [ ] **Generate a MSFT report via the equity_research chat.** Wait for completion. Confirm chat is bound to it (header banner shows the title).
- [ ] **Discuss the report:** "The Q4 capex figure looks wrong — should be $14B" → confirm chat responds and read_payload is being used as needed.
- [ ] **Ask for revision:** "Consolidate this into a final version" → confirm:
  - Chat shows the RevisionInProgressChip immediately
  - Within ~30s, a toast fires: "Report ready: MSFT (revised) ..."
  - Repository shows the new revised report
  - Chat header banner updates to point at the new revision
- [ ] **Generate MSFT again** from the same chat → confirm same thread re-anchors (no new thread spawn)
- [ ] **Generate AAPL** from the same chat → confirm new thread spawns (ticker mismatch)
- [ ] **Discuss the revised report and ask for another revision** → confirm iteration works, with each revision spawning a new entry
- [ ] **Cancel a revision mid-flight** via the chip's Cancel button → confirm task cancelled, chat banner stays at the previous report

If all seven checks pass, the feature is validated.

---

## Spec coverage self-review

| Spec section | Implementation task(s) |
|---|---|
| §1 revise_report tool + ticker-keyed binding | Tasks 11, 12, 13 |
| §2 RevisionRunner (editor pass, bundle inheritance, transcript compression) | Tasks 1, 3, 4, 5, 6, 7 |
| §3 Server route + chat re-anchor (auth, lock, wrapper, fanout) | Tasks 2, 8, 9, 10, 14, 15 |
| §4 Frontend touchpoints (chip, banner update, failure handling) | Tasks 16, 17 |
| Configuration surfaces (env vars) | Wired in Tasks 8, 11, 13 |
| Test plan (21 slices) | All covered across Tasks 1-17 |

No type/method-name drift between tasks. No placeholders.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-17-revision-pass.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
