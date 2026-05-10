# Graph Memory — Runtime Design

Follow-on to the graph memory base subsystem (PR #101). This spec covers the production wiring: when extraction runs, how proposals get reviewed, how vectors get populated, and the cross-cutting timezone subsystem that the schedule depends on.

Distilled from the /grill-me session on 2026-05-10. All decisions reference question IDs in that session.

---

## Decisions

### Extraction trigger and cadence

**Q1: Trigger** — scheduled batch job (not session-close hook, not user-explicit).
**Q2a: Model** — user's `quick` tier (admin-level model config; uses whatever the user picked in setup).
**Q2b: Cadence** — daily at 03:00 in the user's local timezone, with per-user override via Settings.

Rationale: per-session synchronous extraction is too expensive and ties LLM cost to chat latency. Batch nightly amortizes cost. Quick tier handles structured-JSON output well at a fraction of chat-tier cost.

### Timezone subsystem (cross-cutting, prerequisite)

**Q3a / Q4a: Unify timezones** — drop `timezone` columns from `MbSchedule`, `EuSchedule`, `RsSchedule`. Single source of truth: `users.timezone`. Backfill existing rows from each user's earliest existing schedule (or default to `UTC` if no schedules exist).
**Q5: Auto-detection** — frontend captures `Intl.DateTimeFormat().resolvedOptions().timeZone` on login. Server stores it on the user row. On subsequent logins, if the browser TZ differs AND the user has not manually overridden via Settings, silently update. If the user has overridden, ignore browser TZ thereafter.

A `users.timezone_source` enum (`auto | manual`) tracks override state.

### Watermark

**Q3b: High-watermark in an audit table** — new `graph_extraction_runs` table, one row per (user, run). Tracks `started_at`, `finished_at`, `proposals_inserted`, `model_id`, `error`. Watermark = last successful `started_at` per user.

**Q4b: Eligibility** — any session with `updated_at > last_run.started_at`. No closure window; statement-hash tombstones absorb dedup churn across runs.

### What gets extracted

Unchanged from PR #101: LLM produces `proposals[]` with `kind ∈ {user_construct, mention}`. Tightened prompt discipline (claude-mem pattern):
- Hard schema for each kind, listed inline in system prompt
- "Any non-JSON output is discarded" guarantee
- Per-field examples + counter-examples

### Report summary embeddings (#5)

**Q8: Trigger** — same nightly extraction job ingests newly-saved reports.
**Q9: Structured schema** (claude-mem methodology — never embed free prose):

```yaml
subject: str               # already on report row
tagline: str               # already on report.cover
findings: list[str]        # NEW, 2-3 bullets, quick-tier LLM
entities_mentioned: list[str]  # NEW, derived from sections
tone: bullish | bearish | neutral
horizon: short | medium | long
```

Embedded text = `subject || tagline || findings_text`. Other fields stored as columns for pre-filter-then-rank retrieval.

**Q10: Single embedding provider** — same provider for constructs and summaries. Configured once in setup wizard (`text-embedding-3-small` if OpenAI key present, else `nomic-embed-text` via Ollama).

### Recall (#3)

**Q12: One tool, simple signature** — `recall_artifacts(query: str, top_k: int = 5)` returns `[{id, subject, tagline, score}]`. Model decides whether to expand via the existing repo read tool.

**Hybrid retrieval** (claude-mem methodology) — SQLite FTS5 virtual table on `graph_artifact_summaries(summary_text, findings_text)`, combined with cosine over the embedding column. Score = weighted blend (default 0.6 cosine + 0.4 FTS rank). FTS5 ships built-in; no new dep.

### Entity extraction broadening (#6)

**Q14: Substring match against entity values** — for any entity in `graph_entities` where the user has at least one anchored construct, do a case-insensitive substring search in the live message. Minimum length floor (skip values ≤3 chars). Per-entity `is_trigger_disabled` flag for cases like "AI" matching everywhere.

### HTTP routes (#1)

**Q11: REST list + domain-action transitions**:
- `GET /graph/proposals?status=pending` — list user's proposals
- `POST /graph/proposals/{id}/accept` — materialize as construct
- `POST /graph/proposals/{id}/dismiss` — tombstone
- `GET /graph/constructs?entity_id=...` — browse user's beliefs
- `DELETE /graph/constructs/{id}` — retire a construct
- `POST /admin/graph/extract-now?user_id=...` — admin force-run

### Frontend (#4)

**Q13: Standalone Memory page + chat-side drawer**:
- `/memory` sidebar entry, two tabs: "Pending proposals" + "Confirmed beliefs"
- Pending tab: accept/dismiss buttons per row, source-excerpt expandable
- Confirmed tab: grouped by entity, drill-down to provenance
- Chat-side drawer: pulls from right edge of Secretary/ER chat; shows what memory got injected this turn + inline accept/dismiss for any proposals that just landed

Settings additions:
- Timezone (auto-detected, manually overridable)
- Graph extraction time (default 03:00, picker)
- Embedding provider (set once, lock thereafter to avoid corpus migration)

---

## Improvements to already-written code

Findings from studying claude-mem's algorithm prompted these revisions to the slices already on PR #101:

| File | Change |
|---|---|
| `graph_extraction_llm.SYSTEM_PROMPT` | Tighten to per-kind schema with hard rejection. Currently accepts loose JSON. |
| `graph_artifact_summaries` table | Add structured columns (`findings_text`, `entities_mentioned`, `tone`, `horizon`). Keep `summary_text` + `embedding` for backward compat. |
| `graph_artifact_summaries` FTS5 | New virtual table mirroring `summary_text || findings_text` for hybrid retrieval. |
| `graph_user_constructs` | Add `concepts TEXT` column (JSON array of tags). Powers Memory panel grouping and cross-entity recall. |
| `graph_entities` | Add `is_trigger_disabled BOOLEAN DEFAULT 0` for the substring match opt-out. |

---

## Build sequence

Ordered so each slice is independently shippable.

1. **Timezone subsystem MVP** — `users.timezone` column + `users.timezone_source` + capture endpoint + setting up wizard prompt
2. **Unify schedules to read from `users.timezone`** — backfill, drop columns from MB/EU/RS, update scheduler reads
3. **Frontend Settings: timezone picker + auto-detect on login**
4. **`graph_extraction_runs` audit table** + `users.graph_extraction_time` column
5. **Tighten `graph_extraction_llm.SYSTEM_PROMPT`** (already-written code revision)
6. **Scheduled extraction job** — daily user-local-time tick
7. **Admin `POST /admin/graph/extract-now`** — dev iteration tool
8. **Proposal/construct HTTP routes** (5 endpoints)
9. **Artifact summary structured schema** — migration + service layer changes
10. **SQLite FTS5 virtual table on artifact summaries**
11. **Summary generation hook in nightly job** — wire `upsert_artifact_summary` into the extraction sweep
12. **`recall_artifacts` LLM tool wrapper** — single tool, hybrid FTS+cosine
13. **Substring entity extraction** + `is_trigger_disabled` opt-out
14. **Memory page frontend** — `/memory` route, two tabs, CRUD wiring
15. **Chat-side memory drawer** — inline accept/dismiss surface

---

## Deferred / open

- **Auto-accept threshold** — currently every proposal needs user review. A confidence threshold above which proposals auto-accept could come later. Hold for now.
- **Per-section embedding tier** — claude-mem has per-observation embeddings alongside per-session summaries. Useful for "where did I say X about Y" but adds significant indexing cost. Defer until report-level recall proves out.
- **`<private>` opt-out marker** — claude-mem honors a `<private>` tag in user input to exclude content from indexing. Useful for sensitive financial scenarios. Defer until a user asks for it.
- **Multi-tenant FTS5 isolation** — FTS5 virtual tables are global; per-user partitioning is enforced at query time via JOIN. Acceptable for the company-mode user counts we expect.
