// Memory domain fixtures for demo mode. Backs the Memory page's two tabs:
// Pending Proposals (AI-learned beliefs awaiting confirmation) and Confirmed
// Beliefs (accepted constructs grouped by entity). Mirrors the cross-session
// graph-memory routes in api/graph.ts (`/api/graph/...`).
//
// Read-only: accept/dismiss/delete return benign success so the UI's optimistic
// removal sticks without a backend.

import { register, json } from "../registry";
import { daysAgo, hoursAgo } from "../clock";
import type {
  Proposal,
  ProposalListResponse,
  Construct,
  ConstructListResponse,
} from "../../api/graph";

// --- Pending proposals -----------------------------------------------------
// Shaped as `kind: "user_construct"` so ProposalCard renders the statement as
// the primary line and "<construct_kind> on <entity_kind>:<entity_value>" as
// the secondary line, with an expandable source excerpt.

const PENDING_PROPOSALS: Proposal[] = [
  {
    id: "prop-concise-notes",
    kind: "user_construct",
    status: "pending",
    created_at: hoursAgo(5),
    payload: {
      construct_kind: "preference",
      statement: "Prefers concise, thesis-first equity notes over long write-ups",
      entity_kind: "workflow",
      entity_value: "equity_research",
      source_excerpt:
        "\"Keep it tight — lead with the thesis and the two or three numbers that " +
        "actually move it. I skim the rest.\"",
    },
  },
  {
    id: "prop-ai-semis-basket",
    kind: "user_construct",
    status: "pending",
    created_at: hoursAgo(21),
    payload: {
      construct_kind: "watchlist_item",
      statement: "Actively tracks the AI-semiconductor complex: NVDA, AVGO, TSM",
      entity_kind: "theme",
      entity_value: "ai_semiconductors",
      source_excerpt:
        "\"Pull NVDA, AVGO and TSM together whenever you flag AI-infra — I want them " +
        "as one basket, not three separate pings.\"",
    },
  },
  {
    id: "prop-taiwan-exposure",
    kind: "user_construct",
    status: "pending",
    created_at: daysAgo(2),
    payload: {
      construct_kind: "thesis",
      statement: "Wants Taiwan-market exposure expressed through TSMC (2330.TW / TSM ADR)",
      entity_kind: "ticker",
      entity_value: "TSM",
      source_excerpt:
        "\"My Taiwan view is really just a TSMC view. Treat the 2330.TW line and the " +
        "TSM ADR as the same position when you brief me.\"",
    },
  },
  {
    id: "prop-dalio-macro",
    kind: "user_construct",
    status: "pending",
    created_at: daysAgo(4),
    payload: {
      construct_kind: "preference",
      statement: "Frames macro through Ray Dalio's growth/inflation quadrants",
      entity_kind: "framework",
      entity_value: "dalio_macro",
      source_excerpt:
        "\"When you do the macro read, put it in Dalio terms — where are we in the " +
        "growth-vs-inflation quadrant, and what's the debt-cycle backdrop.\"",
    },
  },
  {
    id: "prop-trim-on-rip",
    kind: "user_construct",
    status: "pending",
    created_at: daysAgo(6),
    payload: {
      construct_kind: "concern",
      statement: "Uneasy about position sizing in PLTR after its run — wants trim alerts",
      entity_kind: "ticker",
      entity_value: "PLTR",
      source_excerpt:
        "\"Palantir's gotten big on me. If it rips another leg, nudge me to trim back " +
        "toward a normal weight.\"",
    },
  },
  {
    id: "prop-morning-cadence",
    kind: "user_construct",
    status: "pending",
    created_at: daysAgo(8),
    payload: {
      construct_kind: "preference",
      statement: "Reads the Morning Briefing before the US open; wants it ready by 8am ET",
      entity_kind: "workflow",
      entity_value: "morning_briefing",
      source_excerpt:
        "\"I go through the briefing with coffee. Have it waiting by eight Eastern so " +
        "I'm set before the open.\"",
    },
  },
];

// --- Confirmed beliefs (constructs) ----------------------------------------
// ConstructsList groups by `entity_id` and formats "<kind>:<value>" as
// "<value> (<kind>)". Keep entity_id in that "<kind>:<value>" shape so the
// group headers read cleanly.

function construct(
  overrides: Pick<
    Construct,
    "id" | "kind" | "statement" | "entity_id" | "created_at"
  > & {
    updated_at?: string;
    source_kind?: string;
    source_id?: string;
    source_excerpt?: string;
  },
): Construct {
  const {
    updated_at,
    source_kind,
    source_id,
    source_excerpt,
    ...base
  } = overrides;
  return {
    ...base,
    status: "confirmed",
    updated_at: updated_at ?? base.created_at,
    provenance: {
      source_kind: source_kind ?? "chat",
      source_id: source_id ?? "session-demo",
      source_excerpt: source_excerpt ?? null,
    },
  };
}

const CONFIRMED_CONSTRUCTS: Construct[] = [
  construct({
    id: "con-nvda-core",
    kind: "thesis",
    statement:
      "NVIDIA is a long-term core holding — the AI-infrastructure compute standard",
    entity_id: "ticker:NVDA",
    created_at: daysAgo(41),
    source_kind: "equity_report",
    source_id: "rpt-nvda-2026-06",
    source_excerpt:
      "Confirmed after the Q2 data-center print: \"NVDA stays core. This is the " +
      "compute layer everyone else builds on.\"",
  }),
  construct({
    id: "con-nvda-guardrail",
    kind: "concern",
    statement: "Watches NVIDIA concentration risk — trim if it exceeds ~20% of the book",
    entity_id: "ticker:NVDA",
    created_at: daysAgo(19),
    source_kind: "chat",
    source_excerpt:
      "\"Love it, but I don't want a fifth of everything in one name. Flag me past " +
      "twenty percent.\"",
  }),
  construct({
    id: "con-tsm-taiwan",
    kind: "thesis",
    statement: "TSMC is the preferred vehicle for both foundry leadership and Taiwan exposure",
    entity_id: "ticker:TSM",
    created_at: daysAgo(33),
    source_kind: "chat",
    source_excerpt:
      "\"TSMC is the whole trade — foundry moat plus my Taiwan tilt in one line.\"",
  }),
  construct({
    id: "con-avgo-watch",
    kind: "watchlist_item",
    statement: "Broadcom is on the active watchlist as a custom-silicon / networking play",
    entity_id: "ticker:AVGO",
    created_at: daysAgo(27),
    source_kind: "chat",
    source_excerpt:
      "\"Keep AVGO in the AI-infra basket — custom silicon and the networking side " +
      "are the tell.\"",
  }),
  construct({
    id: "con-ai-semis-theme",
    kind: "thesis",
    statement:
      "AI-semiconductor buildout is the multi-year theme anchoring the portfolio",
    entity_id: "theme:ai_semiconductors",
    created_at: daysAgo(52),
    source_kind: "morning_briefing",
    source_id: "mb-2026-06-16",
    source_excerpt:
      "\"This is the theme I'm underwriting for the next few years — everything else " +
      "is a satellite around it.\"",
  }),
  construct({
    id: "con-dalio-lens",
    kind: "thesis",
    statement: "Reads macro through Ray Dalio's growth/inflation and debt-cycle lens",
    entity_id: "framework:dalio_macro",
    created_at: daysAgo(46),
    source_kind: "chat",
    source_excerpt:
      "\"Give me the Dalio version: which quadrant, and where we sit in the long-term " +
      "debt cycle.\"",
  }),
  construct({
    id: "con-concise-notes",
    kind: "preference",
    statement: "Prefers concise, thesis-first equity notes",
    entity_id: "workflow:equity_research",
    created_at: daysAgo(58),
    updated_at: daysAgo(12),
    source_kind: "chat",
    source_excerpt:
      "\"Lead with the thesis and the numbers that move it. Short is fine.\"",
  }),
  construct({
    id: "con-briefing-cadence",
    kind: "preference",
    statement: "Wants the Morning Briefing delivered before the US open (8am ET)",
    entity_id: "workflow:morning_briefing",
    created_at: daysAgo(37),
    source_kind: "chat",
    source_excerpt:
      "\"Eight Eastern, every trading day — I read it before the bell.\"",
  }),
];

register([
  // List pending proposals. The page always requests status=pending; other
  // statuses have no fixtures, so return an empty list rather than 404.
  {
    method: "GET",
    pattern: "/api/graph/proposals",
    handler: (req) => {
      const status = req.url.searchParams.get("status") ?? "pending";
      const items = status === "pending" ? PENDING_PROPOSALS : [];
      const body: ProposalListResponse = { items };
      return json(body);
    },
  },

  // Accept a proposal -> returns the promoted construct (or null). Read-only:
  // synthesize a benign confirmed construct from the matching proposal.
  {
    method: "POST",
    pattern: "/api/graph/proposals/:id/accept",
    handler: (req) => {
      const proposal = PENDING_PROPOSALS.find((p) => p.id === req.params.id);
      if (!proposal) return json(null);
      const statement =
        typeof proposal.payload.statement === "string"
          ? proposal.payload.statement
          : proposal.kind;
      const entityId =
        typeof proposal.payload.entity_kind === "string" &&
        typeof proposal.payload.entity_value === "string"
          ? `${proposal.payload.entity_kind}:${proposal.payload.entity_value}`
          : "note:general";
      const promoted: Construct = {
        id: `con-${proposal.id}`,
        kind:
          typeof proposal.payload.construct_kind === "string"
            ? proposal.payload.construct_kind
            : "belief",
        status: "confirmed",
        statement,
        entity_id: entityId,
        created_at: hoursAgo(0),
        updated_at: hoursAgo(0),
        provenance: {
          source_kind: "chat",
          source_id: "session-demo",
          source_excerpt:
            typeof proposal.payload.source_excerpt === "string"
              ? proposal.payload.source_excerpt
              : null,
        },
      };
      return json(promoted);
    },
  },

  // Dismiss a proposal -> benign ok.
  {
    method: "POST",
    pattern: "/api/graph/proposals/:id/dismiss",
    handler: () => json({ ok: true }),
  },

  // List confirmed constructs. Optional ?entity_id filter mirrors the real API.
  {
    method: "GET",
    pattern: "/api/graph/constructs",
    handler: (req) => {
      const entityId = req.url.searchParams.get("entity_id");
      const items = entityId
        ? CONFIRMED_CONSTRUCTS.filter((c) => c.entity_id === entityId)
        : CONFIRMED_CONSTRUCTS;
      const body: ConstructListResponse = { items };
      return json(body);
    },
  },

  // Delete a construct -> benign 204-style empty success.
  {
    method: "DELETE",
    pattern: "/api/graph/constructs/:id",
    handler: () => json(null, 200),
  },
]);

export { PENDING_PROPOSALS, CONFIRMED_CONSTRUCTS };
