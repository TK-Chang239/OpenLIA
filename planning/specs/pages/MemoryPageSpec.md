# Memory Page Spec

> **Status:** SHIPPED (behind the graph-memory feature). **Disabled in the public demo build** — the `/memory` route redirects to `/` when `VITE_DEMO_MODE === "true"` (`frontend/src/router/routes.tsx`).
>
> **Grounded in shipped code:** `frontend/src/pages/MemoryPage.tsx`, `frontend/src/components/memory/{ProposalsList,ConstructsList,ProposalCard}.tsx`, `frontend/src/api/graph.ts` (routes under `/api/graph/*`), `frontend/src/router/routes.tsx`.

## Page Overview

The Memory page is the user-facing surface for **cross-session graph memory**: beliefs LIA extracts about the user and their positions. LIA's extractor proposes memory items ("proposals"); the user reviews them and accepts or dismisses each. Accepted proposals become confirmed **constructs** (durable beliefs) that the user can review and delete.

The page is a simple two-tab review surface — no chat, no report generation.

## Page Functionalities

1. **Two tabs** — **Pending proposals** and **Confirmed beliefs** (`memory_page.pending_proposals` / `memory_page.confirmed_beliefs`), rendered as a tablist; Pending is the default.
2. **Pending proposals** (`ProposalsList`) — loads `listProposals('pending')` (`GET /api/graph/proposals?status=pending`). Each proposal (`ProposalCard`) shows the extracted item (kind + payload: construct kind, statement, entity, source excerpt) with two actions:
   - **Accept** → `acceptProposal(id)` (`POST /api/graph/proposals/{id}/accept`). Optimistically removes the row; on success the proposal is promoted to a confirmed construct.
   - **Dismiss** → `dismissProposal(id)` (`POST /api/graph/proposals/{id}/dismiss`). Removes the proposal.
   Actions are per-row busy-guarded; failures roll back the optimistic update and toast an error.
3. **Confirmed beliefs** (`ConstructsList`) — loads `listConstructs()` (`GET /api/graph/constructs`). Each construct shows its statement, kind (position / thesis / concern / watchlist_item / …), the entity it is about, and provenance (source excerpt). A **delete** action calls `deleteConstruct(id)` (`DELETE /api/graph/constructs/{id}`).

## Page Design

### Layout

- Full-height flex column. A 52px header: title (`memory_page.title`) + a mono subtitle divider (`memory_page.subtitle`).
- Body: a scrollable centered column (`max-w-3xl`) with a fade-up entrance.
- Tablist: two `role="tab"` buttons with an active underline (`border-accent-primary text-accent-primary`); the selected tab controls a `role="tabpanel"` region rendering either `ProposalsList` or `ConstructsList`.

### Data contract (`api/graph.ts`)

| Type | Fields (shipped) |
|---|---|
| `Proposal` | `id, kind, payload, status (pending/accepted/dismissed), created_at` |
| `ProposalPayload` | `construct_kind?, statement?, entity_kind?, entity_value?, source_excerpt?, artifact_kind?, artifact_id?` |
| `Construct` | `id, kind, status, statement, entity_id, created_at, updated_at, provenance?` |

## States

| State | Description |
|---|---|
| **Loading** | Each list fetches on mount; nulls render a loading placeholder. |
| **Pending populated** | Proposal cards with Accept / Dismiss. |
| **Confirmed populated** | Construct cards with Delete. |
| **Empty** | Empty-state copy per tab when a list returns no items. |
| **Error** | Inline error text on load failure; per-action failures toast and roll back. |
| **Demo** | Route disabled — redirects to Home. |

## Configurations

- **LLM:** none on this page. Proposals are produced by the graph-memory extractor elsewhere; this page only reviews/curates them.
- **Backend:** `packages/server/src/openlia_server/routes/graph.py`, mounted under `/graph`.
