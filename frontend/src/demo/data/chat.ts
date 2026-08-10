// Chat / Secretary domain fixtures for demo mode.
//
// Powers three surfaces:
//   1. Home "recent" strip  — listSessions() -> { items: ChatSession[] }.
//   2. Secretary page load  — a rich completed conversation replayed from the
//      messages endpoint (a couple of user turns, assistant replies, tool-call
//      chips and a clickable report thumbnail chip with citations).
//   3. Live streaming reply  — if the user sends a message, the Secretary
//      stream endpoint replays a scripted chat.start -> chat.token* ->
//      chat.done SSE script so the demo streams live.
//
// Read-only: session mutations (create/patch/delete/model) return benign
// success so the UI's optimistic paths resolve without a backend.

import {
  register,
  json,
  notFound,
  type DemoRequest,
  type SseFrame,
} from "../registry";
import { DEMO_NOW_ISO, minsAgo, hoursAgo, daysAgo } from "../clock";
import { companyName } from "./persona";

// --- Session fixtures --------------------------------------------------------
// department values are the backend slugs (see api/departments.ts); RecentStrip
// deep-links them via navData's departmentId map. created_at is spread across
// the demo timeline so the recent strip and history sort naturally.

const NVDA_SESSION_ID = "demo-chat-secretary-nvda";

interface DemoSession {
  id: string;
  department: string;
  title: string;
  created_at: string;
}

const SESSIONS: DemoSession[] = [
  {
    id: NVDA_SESSION_ID,
    department: "secretary",
    title: `${companyName("NVDA")} data-center demand`,
    created_at: minsAgo(24),
  },
  {
    id: "demo-chat-secretary-terms",
    department: "secretary",
    title: "Explain free cash flow yield",
    created_at: hoursAgo(5),
  },
  {
    id: "demo-chat-equity-avgo",
    department: "equity_research",
    title: `${companyName("AVGO")} initiation notes`,
    created_at: hoursAgo(21),
  },
  {
    id: "demo-chat-macro-rates",
    department: "macro_research",
    title: "Rate-cut path into year-end",
    created_at: daysAgo(2),
  },
  {
    id: "demo-chat-earnings-msft",
    department: "earnings_update",
    title: `${companyName("MSFT")} cloud print`,
    created_at: daysAgo(4),
  },
];

/** Full ChatSession shape the api/chat client expects. */
function toSession(s: DemoSession) {
  return {
    id: s.id,
    department: s.department,
    title: s.title,
    is_pinned: false,
    is_archived: false,
    created_at: s.created_at,
    model_id: "demo-model",
    disabled_connector_ids: [],
    disabled_skill_ids: [],
    response_length: "normal",
    attached_report_id: null,
  };
}

function sessionById(id: string): DemoSession | undefined {
  return SESSIONS.find((s) => s.id === id);
}

// --- Completed conversation for the NVDA secretary session -------------------
// Rendered on load by ChatInterface via listMessages(). Assistant turns carry
// tool_calls (rendered as source chips) — one chip is a clickable report
// thumbnail (structured.report_id) and others are citations (news / market
// data / repository).

const NVDA_REPORT_ID = "demo-report-nvda-dc";

function msgUser(id: string, content: string, createdAt: string) {
  return {
    id,
    role: "user" as const,
    content,
    tool_calls: null,
    model_ref: null,
    token_usage: null,
    created_at: createdAt,
    attachments: [],
  };
}

function msgAssistant(
  id: string,
  content: string,
  createdAt: string,
  toolCalls: Array<Record<string, unknown>> | null,
  totalTokens: number,
) {
  return {
    id,
    role: "assistant" as const,
    content,
    tool_calls: toolCalls,
    model_ref: "demo-model",
    token_usage: { total_tokens: totalTokens },
    created_at: createdAt,
    attachments: [],
  };
}

const NVDA_MESSAGES = [
  msgUser(
    "m1",
    "Give me a quick read on NVDA data-center demand right now.",
    minsAgo(24),
  ),
  msgAssistant(
    "m2",
    [
      "## Snapshot",
      "",
      "Data-center remains the driver: the segment is the bulk of revenue and " +
        "still growing on accelerator demand. Supply is easing versus last year, " +
        "and next-generation parts are ramping into the channel.",
      "",
      "- **Demand:** broad across hyperscalers and enterprise AI build-outs.",
      "- **Supply:** advanced-packaging capacity is the binding constraint, loosening gradually.",
      "- **Watch item:** customer concentration among a handful of large buyers.",
      "",
      "This is an illustrative demo summary, not investment advice.",
    ].join("\n"),
    minsAgo(23),
    [
      {
        call_id: "tc-quote-nvda",
        tool_name: "get_market_quote",
        args_preview: 'ticker="NVDA"',
        status: "done",
        summary: "Market data — NVDA",
        structured: { ticker: "NVDA", price: 176.2, day_change_pct: 1.9 },
      },
      {
        call_id: "tc-news-nvda",
        tool_name: "search_news",
        args_preview: 'query="NVDA data center demand"',
        status: "done",
        summary: "Accelerator demand stays broad into H2",
        structured: {
          headline: "Accelerator demand stays broad into H2",
          source: "Demo Newswire",
        },
      },
    ],
    640,
  ),
  msgUser(
    "m3",
    "Can you pull together a short data-center demand brief I can save?",
    minsAgo(21),
  ),
  msgAssistant(
    "m4",
    [
      "I compiled a short brief covering demand breadth, the supply constraint, " +
        "and the main risk. It's saved to your repository — open the card below " +
        "to read it.",
      "",
      "Key points: demand is broad-based, advanced-packaging supply is the gating " +
        "factor, and buyer concentration is the risk to track. Again, illustrative " +
        "demo content only.",
    ].join("\n"),
    minsAgo(20),
    [
      {
        call_id: "tc-repo-read",
        tool_name: "read_repo_item",
        args_preview: 'filename="nvda-watchlist-notes.md"',
        status: "done",
        summary: "nvda-watchlist-notes.md",
        structured: { filename: "nvda-watchlist-notes.md" },
      },
      {
        call_id: "tc-report-nvda",
        tool_name: "generate_report",
        args_preview: 'title="NVDA Data-Center Demand Brief"',
        status: "done",
        summary: "NVDA Data-Center Demand Brief",
        structured: {
          report_id: NVDA_REPORT_ID,
          title: "NVDA Data-Center Demand Brief",
          filename: "nvda-data-center-brief.md",
        },
      },
    ],
    880,
  ),
];

const MESSAGES_BY_SESSION: Record<string, ReturnType<typeof msgUser | typeof msgAssistant>[]> = {
  [NVDA_SESSION_ID]: NVDA_MESSAGES,
};

// --- Scripted streaming reply ------------------------------------------------
// If the user sends any message, replay a coherent 2-3 sentence answer as a
// token stream. Frame format matches useChatStream's parser exactly: each SSE
// frame carries a named `event:` line plus a JSON `data:` payload.

const REPLY_SENTENCES =
  "Data-center demand for NVDA looks broad-based across the large cloud buyers, " +
  "with advanced-packaging supply still the main constraint. The next-generation " +
  "parts are ramping, so unit availability should improve gradually. This is an " +
  "illustrative demo response and not investment advice.";

/** Split a string into token-ish chunks (word + trailing space) for streaming. */
function tokenize(text: string): string[] {
  return text.match(/\S+\s*/g) ?? [text];
}

function replyFrames(): SseFrame[] {
  const frames: SseFrame[] = [
    { event: "chat.start", data: {}, delayMs: 120 },
  ];
  const tokens = tokenize(REPLY_SENTENCES);
  for (const tok of tokens) {
    // 40-90ms per token, jittered so it feels live.
    const delayMs = 40 + Math.floor(Math.random() * 50);
    frames.push({ event: "chat.token", data: { text: tok }, delayMs });
  }
  frames.push({
    event: "chat.done",
    data: { token_usage: { total_tokens: 420 } },
    delayMs: 60,
  });
  return frames;
}

// --- Routes ------------------------------------------------------------------

register([
  // List sessions (Home recent strip + Secretary page's initial pick).
  {
    method: "GET",
    pattern: "/api/chat/sessions",
    handler: (req: DemoRequest) => {
      const dept = req.url.searchParams.get("department");
      const items = SESSIONS.filter((s) => !dept || s.department === dept).map(
        toSession,
      );
      return json({ items });
    },
  },

  // Single session (ChatInterface refreshes tool/response-length state on mount;
  // SecretaryPage's onSelect reads the title).
  {
    method: "GET",
    pattern: "/api/chat/sessions/:id",
    handler: (req: DemoRequest) => {
      const s = sessionById(req.params.id);
      if (!s) return notFound("session_not_found");
      return json(toSession(s));
    },
  },

  // Default session for a department (fallback lookup used by some flows).
  {
    method: "GET",
    pattern: "/api/chat/sessions/by-department/:department",
    handler: (req: DemoRequest) => {
      const s = SESSIONS.find((x) => x.department === req.params.department);
      if (!s) return notFound("no_session");
      return json(toSession(s));
    },
  },

  // Messages for a session — the completed conversation shown on load.
  {
    method: "GET",
    pattern: "/api/chat/sessions/:id/messages",
    handler: (req: DemoRequest) => {
      const items = MESSAGES_BY_SESSION[req.params.id] ?? [];
      return json({ items });
    },
  },

  // Create session — return a benign new-session record echoing the request.
  {
    method: "POST",
    pattern: "/api/chat/sessions",
    handler: (req: DemoRequest) => {
      const body = (req.body ?? {}) as {
        department?: string;
        title?: string;
        attached_report_id?: string;
      };
      return json({
        id: `demo-chat-new-${Date.now()}`,
        department: body.department ?? "secretary",
        title: body.title ?? "New chat",
        is_pinned: false,
        is_archived: false,
        created_at: DEMO_NOW_ISO,
        model_id: "demo-model",
        disabled_connector_ids: [],
        disabled_skill_ids: [],
        response_length: "normal",
        attached_report_id: body.attached_report_id ?? null,
      });
    },
  },

  // Rename / pin / archive / tool toggles — accepted, no-op.
  {
    method: "PATCH",
    pattern: "/api/chat/sessions/:id",
    handler: () => json({ ok: true }),
  },

  // Delete — accepted, no content.
  {
    method: "DELETE",
    pattern: "/api/chat/sessions/:id",
    handler: () => json(null, 204),
  },

  // Set per-session model — accepted, no-op.
  {
    method: "PUT",
    pattern: "/api/chat/sessions/:id/model",
    handler: () => json({ ok: true }),
  },

  // Secretary streaming reply. SecretaryPage points ChatInterface at this URL
  // (streamUrl="/api/departments/secretary/chat"); replay the scripted answer.
  {
    method: "POST",
    pattern: "/api/departments/secretary/chat",
    handler: () => ({ sse: replyFrames() }),
  },

  // Default chat-stream endpoint (used when no streamUrl override is passed).
  {
    method: "POST",
    pattern: "/api/chat/sessions/:id/stream",
    handler: () => ({ sse: replyFrames() }),
  },
]);
