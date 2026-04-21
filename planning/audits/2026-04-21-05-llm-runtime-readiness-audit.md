# LLM Runtime Readiness Audit

Date: 2026-04-21

Scope: core runtime runners, tool loop, runtime event contract, cancellation,
model/provider resolution, and department readiness for report/chat routes.

Validation commands run: none. Static audit only.

## Executive Summary

The runtime is more ready than older audits suggested: `ChatRunner` and
`ReportRunner` now have bounded multi-round tool loops. However, the product
still lacks server routes that expose the runtime, future plans still use stale
runtime imports in several snippets, and provider resolution edge cases remain
important to harden before department routes depend on them.

## Current Runtime Baseline

Implemented:

- `ChatRunner`
- `ReportRunner`
- `BatchRunner`
- `ReportRequest`
- runtime event dataclasses
- `to_wire(event)`
- cancellation token polling
- framework/style-guide package data

Not implemented in server/product surface:

- chat SSE route
- report SSE route
- report persistence service
- report export route
- department route factories

## Findings

### 1. High - No Current Server Route Exercises Runtime End To End

The core runners exist, but no backend route currently calls them for chat or
report generation.

Impact: runtime behavior is unit-level only until Plan 12/13. Product flow
risks remain hidden.

Required fix:

- First runtime route should be Secretary chat or report smoke route.
- It must serialize `to_wire(event)` into SSE frames.
- It must cancel on client disconnect.
- It must be tested through `create_app()` or mounted router factory.

### 2. High - Future Plans Still Use Wrong Runtime Imports

Plan 14 still has `openlia.runtime.requests.ReportRequest` and
`openlia.runtime.sse`. Plan 15 still uses `serialize_sse`.

Impact: future department implementation will fail unless snippets are
rewritten.

Required fix:

- Replace with `openlia.llm.runtime.messages.ReportRequest`.
- Replace with `openlia.llm.runtime.events.to_wire`.
- If a server helper for SSE frames is desired, add it explicitly before use.

### 3. Medium - Tool Loop Needs Product-Level Regression Tests

Current source has bounded loops in chat/report. It should be protected by
tests that prove:

- provider calls tool in round 1
- provider calls a second tool in round 2
- provider returns no more tool calls
- final answer/report uses both tool results
- `find_more_data` can add a tool for a later round
- max rounds stops runaway calls predictably

Impact: future refactors can regress to one-round behavior without product
tests.

### 4. Medium - Disabled Provider Resolution Needs Hardening Confirmation

Older audit found enabled models on disabled providers could raise raw runtime
errors. This audit did not re-verify the registry implementation deeply.

Required follow-up:

- Confirm registry filters both model and provider enabled state.
- Confirm fallback to another enabled model.
- Confirm no usable model raises `TierNotConfiguredError`.
- Confirm runners emit `chat.error` / `report.error`.

### 5. Medium - Report Schema Validation Is Not Yet In Product Path

`ReportRunner` parses final JSON and emits `ReportComplete(schema=...)`. Plan
13 will add schema validation and report store. Until that lands, malformed but
JSON-shaped report payloads can pass through.

Required fix:

- Plan 13 report store must validate before persisting.
- Invalid schema should emit or translate to a controlled `report.error`.

### 6. Medium - Cancellation Is Polling-Based But Needs Route Tests

Runners poll `CancellationToken`. Server routes that watch
`request.is_disconnected()` do not exist yet.

Required tests:

- disconnect flips token
- runner stops without terminal event
- no partial report row is persisted
- scheduler cancellation still marks jobs correctly

## Readiness Gate For Department Plans

Before Plan 14/15 department implementation:

1. One chat SSE route works.
2. One report SSE route works.
3. `to_wire` framing is tested.
4. report persistence is validated.
5. disabled provider/model cases emit runtime errors, not HTTP 500s.
