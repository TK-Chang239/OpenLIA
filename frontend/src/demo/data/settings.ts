// Settings-domain fixtures: user prefs, models (roster + admin catalog + slot
// defaults + per-department overrides), connectors, skills, report templates,
// guardrail activity, cache stats, and the active-session panel. These answers
// let every Settings section render populated in the demo (personal mode, where
// the single local user is an admin, so admin-gated sections also show).
//
// Read-only: every write verb (PATCH/PUT/POST/DELETE for prefs, connectors,
// models, slots, sessions, ...) returns a benign success echo. Nothing persists.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, daysAgo } from "../clock";
import { INVESTOR } from "./persona";

// --- Model identity, shared across every models endpoint -------------------
// One roster of enabled models, referenced by id from prefs, admin catalog,
// slot defaults, and per-department overrides so selections resolve cleanly.

const PROVIDERS = [
  {
    id: "prov-anthropic",
    kind: "anthropic" as const,
    label: "Anthropic",
    env_var_name: "ANTHROPIC_API_KEY",
    base_url: null as string | null,
  },
  {
    id: "prov-openai",
    kind: "openai" as const,
    label: "OpenAI",
    env_var_name: "OPENAI_API_KEY",
    base_url: null as string | null,
  },
  {
    id: "prov-ollama",
    kind: "ollama" as const,
    label: "Ollama (local)",
    env_var_name: null as string | null,
    base_url: "http://localhost:11434",
  },
];

interface DemoModel {
  id: string;
  provider_id: string;
  provider_kind: string;
  model_ref: string;
  display_name: string;
  web_search_native: boolean;
}

const MODELS: DemoModel[] = [
  {
    id: "model-claude-sonnet",
    provider_id: "prov-anthropic",
    provider_kind: "anthropic",
    model_ref: "claude-sonnet-4-5",
    display_name: "Claude Sonnet 4.5",
    web_search_native: true,
  },
  {
    id: "model-gpt-54",
    provider_id: "prov-openai",
    provider_kind: "openai",
    model_ref: "gpt-5.4",
    display_name: "GPT-5.4",
    web_search_native: true,
  },
  {
    id: "model-llama-local",
    provider_id: "prov-ollama",
    provider_kind: "ollama",
    model_ref: "llama3.3:70b",
    display_name: "Llama 3.3 70B (local)",
    web_search_native: false,
  },
];

const PREFERRED_MODEL_ID = "model-claude-sonnet";

// RosterEntry[] — the non-admin "enabled models" list used by pickers and the
// per-department / system-role dropdowns.
const ROSTER = MODELS.map((m) => ({
  id: m.id,
  model_ref: m.model_ref,
  display_name: m.display_name,
  provider_id: m.provider_id,
  provider_kind: m.provider_kind,
  is_enabled: true,
}));

// AdminModel[] grouped by provider, for the admin ProviderCatalog.
const modelsForProvider = (providerId: string) =>
  MODELS.filter((m) => m.provider_id === providerId).map((m) => ({
    id: m.id,
    provider_id: m.provider_id,
    model_ref: m.model_ref,
    display_name: m.display_name,
    is_enabled: true,
    overrides: null,
  }));

// Registered department slugs (drives the per-department override rows).
const DEPARTMENT_IDS = [
  "secretary",
  "equity_research",
  "earnings_update",
  "morning_briefing",
  "retail_sentiment",
  "macro_research",
  "panic_thermometer",
];

// --- User preferences ------------------------------------------------------

const PREFS = {
  display_name: INVESTOR.displayName,
  theme: "system" as const,
  notify_inapp: true,
  notify_email: false,
  display_language: "en" as const,
  response_language: "en" as const,
  report_language: "en" as const,
  preferred_model_id: PREFERRED_MODEL_ID,
  timezone: "America/New_York",
  timezone_source: "manual" as const,
  graph_extraction_time: "03:00",
};

// --- Connectors ------------------------------------------------------------
// A few configured connectors, all validated, secrets masked (never real).

const CONNECTOR_ROWS = [
  {
    id: "conn-eodhd",
    provider_id: "eodhd",
    display_name: "EODHD Financial Data",
    source: "built_in" as const,
    category: "financial" as const,
    status: "validated" as const,
    last_error: null,
    cached_tools_count: 12,
  },
  {
    id: "conn-newsapi",
    provider_id: "newsapi",
    display_name: "NewsAPI",
    source: "built_in" as const,
    category: "news" as const,
    status: "validated" as const,
    last_error: null,
    cached_tools_count: 3,
  },
  {
    id: "conn-firecrawl",
    provider_id: "firecrawl",
    display_name: "Firecrawl Web Search",
    source: "remote_mcp" as const,
    category: "web_search" as const,
    status: "validated" as const,
    last_error: null,
    cached_tools_count: 5,
  },
  {
    id: "conn-x-social",
    provider_id: "x_social",
    display_name: "X (social sentiment)",
    source: "cli_mcp" as const,
    category: "social" as const,
    status: "validated" as const,
    last_error: null,
    cached_tools_count: 4,
  },
];

// ConnectorDetail for the edit modal — secret *key names* only, no values.
const CONNECTOR_DETAIL: Record<string, unknown> = {
  "conn-eodhd": {
    ...CONNECTOR_ROWS[0],
    launch: { modes: [{ kind: "built_in", env_keys: ["EODHD_API_KEY"] }] },
    secret_keys: ["EODHD_API_KEY"],
    source_repo_url: null,
    source_repo_revision: null,
    grounding_paths: null,
    openapi_url: null,
    grounding_status: "ready",
    cached_repo_commit_sha: null,
  },
  "conn-newsapi": {
    ...CONNECTOR_ROWS[1],
    launch: { modes: [{ kind: "built_in", env_keys: ["NEWSAPI_KEY"] }] },
    secret_keys: ["NEWSAPI_KEY"],
    source_repo_url: null,
    source_repo_revision: null,
    grounding_paths: null,
    openapi_url: null,
    grounding_status: "none",
    cached_repo_commit_sha: null,
  },
  "conn-firecrawl": {
    ...CONNECTOR_ROWS[2],
    launch: {
      modes: [
        {
          kind: "remote_mcp",
          url: "https://mcp.firecrawl.dev/v1",
          headers: { Authorization: "Bearer ****" },
        },
      ],
    },
    secret_keys: ["FIRECRAWL_API_KEY"],
    source_repo_url: null,
    source_repo_revision: null,
    grounding_paths: null,
    openapi_url: null,
    grounding_status: "ready",
    cached_repo_commit_sha: null,
  },
  "conn-x-social": {
    ...CONNECTOR_ROWS[3],
    launch: {
      modes: [
        { kind: "cli_mcp", argv: ["npx", "x-mcp"], env_keys: ["X_BEARER_TOKEN"] },
      ],
    },
    secret_keys: ["X_BEARER_TOKEN"],
    source_repo_url: null,
    source_repo_revision: null,
    grounding_paths: null,
    openapi_url: null,
    grounding_status: "none",
    cached_repo_commit_sha: null,
  },
};

// Built-in connector catalog (shown when the user clicks "add from catalog").
const BUILTIN_TEMPLATES = [
  {
    template_id: "eodhd",
    display_name: "EODHD Financial Data",
    category: "financial" as const,
    api_key_env_var: "EODHD_API_KEY",
    covered_need_ids: ["financials", "prices", "fundamentals"],
  },
  {
    template_id: "newsapi",
    display_name: "NewsAPI",
    category: "news" as const,
    api_key_env_var: "NEWSAPI_KEY",
    covered_need_ids: ["headlines"],
  },
];

// --- Skills ----------------------------------------------------------------

const SKILLS = [
  {
    skill_id: "sec-filings-reader",
    display_name: "SEC Filings Reader",
    description: "Pull and summarize 10-K / 10-Q filings for a ticker.",
    version: "1.2.0",
    departments: ["equity_research", "earnings_update"],
    scope: "system" as const,
    enabled: true,
    source: "built-in",
    installed_at: daysAgo(40),
  },
  {
    skill_id: "dcf-modeler",
    display_name: "DCF Modeler",
    description: "Build a discounted-cash-flow scaffold from consensus inputs.",
    version: "0.9.1",
    departments: ["equity_research"],
    scope: "user" as const,
    enabled: true,
    source: "git",
    installed_at: daysAgo(9),
  },
];

// --- Report templates ------------------------------------------------------

const REPORT_TEMPLATES = [
  {
    id: "tmpl-initiation",
    name: "Equity Initiation",
    template_spec: {
      template_id: "tmpl-initiation",
      name: "Equity Initiation",
      shape_description: "Full initiation of coverage.",
      ticker_anchored: true,
      sections: [],
    },
    source_markdown: null,
    created_at: daysAgo(60),
    updated_at: daysAgo(12),
  },
  {
    id: "tmpl-quick-take",
    name: "Quick Take",
    template_spec: {
      template_id: "tmpl-quick-take",
      name: "Quick Take",
      shape_description: "One-page thesis snapshot.",
      ticker_anchored: true,
      sections: [],
    },
    source_markdown: null,
    created_at: daysAgo(30),
    updated_at: daysAgo(3),
  },
];

// --- Guardrail activity ----------------------------------------------------

const GUARDRAIL_EVENTS = [
  {
    id: "grd-1",
    created_at: daysAgo(1),
    session_id: "sess-er-01",
    user_id: "local",
    department_id: "equity_research",
    event_type: "tripwire_flag" as const,
    category: "no_price_targets",
    action_taken: "warned" as const,
    tripwire_pattern: "price target",
    response_excerpt: "Adjusted phrasing to avoid an explicit price target.",
    model_ref: "claude-sonnet-4-5",
  },
  {
    id: "grd-2",
    created_at: daysAgo(4),
    session_id: "sess-sec-02",
    user_id: "local",
    department_id: "secretary",
    event_type: "persona_refusal" as const,
    category: "no_advice",
    action_taken: "replaced" as const,
    tripwire_pattern: null,
    response_excerpt: "Declined to give personalized buy/sell advice.",
    model_ref: "gpt-5.4",
  },
];

// --- Active sessions -------------------------------------------------------

const AUTH_SESSIONS = [
  {
    id: "sess-current",
    created_at: daysAgo(2),
    last_seen_at: DEMO_NOW_ISO,
    expires_at: daysAgo(-28), // ~28 days in the future
    user_agent: "Chrome on macOS",
    ip_address: "127.0.0.1",
    current: true,
  },
];

register([
  // --- User preferences ----------------------------------------------------
  {
    method: "GET",
    pattern: "/api/settings/prefs",
    handler: () => json(PREFS),
  },
  {
    method: "PATCH",
    pattern: "/api/settings/prefs",
    handler: (req) => json({ ...PREFS, ...(req.body as object | null) }),
  },
  {
    method: "PUT",
    pattern: "/api/settings/timezone",
    handler: (req) => {
      const b = (req.body ?? {}) as { timezone?: string; source?: string };
      return json({
        ...PREFS,
        timezone: b.timezone ?? PREFS.timezone,
        timezone_source: b.source === "auto" ? "auto" : "manual",
      });
    },
  },
  {
    method: "PUT",
    pattern: "/api/settings/graph-extraction-time",
    handler: (req) => {
      const b = (req.body ?? {}) as { time?: string };
      return json({ ...PREFS, graph_extraction_time: b.time ?? PREFS.graph_extraction_time });
    },
  },
  {
    method: "PATCH",
    pattern: "/api/settings/email",
    handler: (req) => {
      const b = (req.body ?? {}) as { new_email?: string };
      return json({ email: b.new_email ?? "demo@example.com" });
    },
  },

  // --- Models: roster + registered departments -----------------------------
  {
    method: "GET",
    pattern: "/api/settings/enabled-models",
    handler: () => json(ROSTER),
  },
  {
    method: "GET",
    pattern: "/api/settings/departments",
    handler: () => json({ departments: DEPARTMENT_IDS }),
  },

  // --- Models: admin provider/model catalog --------------------------------
  {
    method: "GET",
    pattern: "/api/settings/admin/llm/providers",
    handler: () =>
      json(
        PROVIDERS.map((p) => ({
          id: p.id,
          kind: p.kind,
          label: p.label,
          has_api_key: p.kind !== "ollama",
          env_var_name: p.env_var_name,
          base_url: p.base_url,
          is_enabled: true,
          test: { ok: true, latency_ms: 240, error_class: null, error_msg: null },
        })),
      ),
  },
  {
    method: "GET",
    pattern: "/api/settings/admin/llm/providers/:id/models",
    handler: (req) => json(modelsForProvider(req.params.id)),
  },
  {
    method: "POST",
    pattern: "/api/settings/admin/llm/providers",
    handler: (req) => {
      const b = (req.body ?? {}) as { kind?: string; label?: string };
      return json({
        id: "prov-demo",
        kind: b.kind ?? "openai",
        label: b.label ?? "Demo provider",
        has_api_key: true,
        env_var_name: null,
        base_url: null,
        is_enabled: true,
        test: { ok: true, latency_ms: 200, error_class: null, error_msg: null },
      });
    },
  },
  {
    method: "PUT",
    pattern: "/api/settings/admin/llm/providers/:id",
    handler: (req) => {
      const p = PROVIDERS[0];
      return json({
        id: req.params.id,
        kind: p.kind,
        label: p.label,
        has_api_key: true,
        env_var_name: p.env_var_name,
        base_url: p.base_url,
        is_enabled: true,
        test: null,
      });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/settings/admin/llm/providers/:id",
    handler: () => json({ ok: true }, 204),
  },
  {
    method: "POST",
    pattern: "/api/settings/admin/llm/providers/test",
    handler: () =>
      json({ ok: true, latency_ms: 220, error_class: null, error_msg: null }),
  },
  {
    method: "POST",
    pattern: "/api/settings/admin/llm/models",
    handler: (req) => {
      const b = (req.body ?? {}) as {
        provider_id?: string;
        model_ref?: string;
        display_name?: string;
      };
      return json({
        id: "model-demo",
        provider_id: b.provider_id ?? "prov-openai",
        model_ref: b.model_ref ?? "demo-model",
        display_name: b.display_name ?? "Demo model",
        is_enabled: true,
        overrides: null,
      });
    },
  },
  {
    method: "PUT",
    pattern: "/api/settings/admin/llm/models/:id",
    handler: (req) => {
      const b = (req.body ?? {}) as {
        provider_id?: string;
        model_ref?: string;
        display_name?: string;
      };
      return json({
        id: req.params.id,
        provider_id: b.provider_id ?? "prov-openai",
        model_ref: b.model_ref ?? "demo-model",
        display_name: b.display_name ?? "Demo model",
        is_enabled: true,
        overrides: null,
      });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/settings/admin/llm/models/:id",
    handler: () => json({ ok: true }, 204),
  },

  // --- Models: slot defaults (department + system_role) --------------------
  {
    method: "GET",
    pattern: "/api/settings/admin/llm/slot-defaults",
    handler: () =>
      json({
        defaults: [
          { slot_kind: "department", slot_id: "equity_research", model_id: PREFERRED_MODEL_ID },
          { slot_kind: "department", slot_id: "morning_briefing", model_id: "model-gpt-54" },
          { slot_kind: "system_role", slot_id: "graph_extraction", model_id: "model-llama-local" },
          { slot_kind: "system_role", slot_id: "graph_summarization", model_id: PREFERRED_MODEL_ID },
        ],
      }),
  },
  {
    method: "PUT",
    pattern: "/api/settings/admin/llm/slot-defaults/:slot_kind/:slot_id",
    handler: (req) => {
      const b = (req.body ?? {}) as { model_id?: string };
      return json({
        slot_kind: req.params.slot_kind,
        slot_id: req.params.slot_id,
        model_id: b.model_id ?? PREFERRED_MODEL_ID,
      });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/settings/admin/llm/slot-defaults/:slot_kind/:slot_id",
    handler: () => json({ ok: true }, 204),
  },

  // --- Models: per-department user overrides -------------------------------
  {
    method: "GET",
    pattern: "/api/departments/:slug/model-pref",
    handler: (req) =>
      json({
        department_id: req.params.slug,
        model_id: null,
        effective_model_id: PREFERRED_MODEL_ID,
      }),
  },
  {
    method: "PUT",
    pattern: "/api/departments/:slug/model-pref",
    handler: (req) => {
      const b = (req.body ?? {}) as { model_id?: string };
      return json({
        department_id: req.params.slug,
        model_id: b.model_id ?? PREFERRED_MODEL_ID,
        effective_model_id: b.model_id ?? PREFERRED_MODEL_ID,
      });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/departments/:slug/model-pref",
    handler: () => json({ ok: true }, 204),
  },

  // --- Connectors ----------------------------------------------------------
  {
    method: "GET",
    pattern: "/api/connectors",
    handler: () => json(CONNECTOR_ROWS),
  },
  {
    method: "GET",
    pattern: "/api/connectors/builtins",
    handler: () => json(BUILTIN_TEMPLATES),
  },
  {
    method: "GET",
    pattern: "/api/connectors/:id",
    handler: (req) => {
      const detail = CONNECTOR_DETAIL[req.params.id];
      return detail ? json(detail) : notFound();
    },
  },
  {
    method: "POST",
    pattern: "/api/connectors",
    handler: (req) => {
      const b = (req.body ?? {}) as {
        provider_id?: string;
        display_name?: string;
        source?: string;
        category?: string;
      };
      return json({
        id: "conn-demo",
        provider_id: b.provider_id ?? "demo",
        display_name: b.display_name ?? "Demo connector",
        source: b.source ?? "built_in",
        category: b.category ?? "financial",
        status: "validated",
        last_error: null,
        cached_tools_count: 0,
      });
    },
  },
  {
    method: "PUT",
    pattern: "/api/connectors/:id",
    handler: (req) => {
      const row =
        CONNECTOR_ROWS.find((r) => r.id === req.params.id) ?? CONNECTOR_ROWS[0];
      const b = (req.body ?? {}) as { display_name?: string };
      return json({ ...row, display_name: b.display_name ?? row.display_name });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/connectors/:id",
    handler: () => json({ ok: true }, 204),
  },
  {
    method: "POST",
    pattern: "/api/connectors/:id/validate",
    handler: (req) => {
      const row =
        CONNECTOR_ROWS.find((r) => r.id === req.params.id) ?? CONNECTOR_ROWS[0];
      return json({ ...row, status: "validated", last_error: null });
    },
  },
  {
    method: "POST",
    pattern: "/api/connectors/:id/sync-template-specs",
    handler: () => json({ inserted: 0 }),
  },
  {
    method: "POST",
    pattern: "/api/connectors/install-builtin",
    handler: (req) => {
      const b = (req.body ?? {}) as { template_id?: string };
      const tmpl = BUILTIN_TEMPLATES.find((t) => t.template_id === b.template_id);
      return json({
        id: `conn-${b.template_id ?? "demo"}`,
        provider_id: b.template_id ?? "demo",
        display_name: tmpl?.display_name ?? "Demo connector",
        source: "built_in",
        category: tmpl?.category ?? "financial",
        status: "validated",
        last_error: null,
        cached_tools_count: 0,
      });
    },
  },
  {
    method: "POST",
    pattern: "/api/connectors/introspect-python-lib",
    handler: () => json({ params: [] }),
  },
  {
    method: "POST",
    pattern: "/api/connectors/install-python-package",
    handler: () => json({ stdout: "demo: no packages installed" }),
  },

  // --- Skills --------------------------------------------------------------
  {
    method: "GET",
    pattern: "/api/skills",
    handler: () => json({ items: SKILLS }),
  },
  {
    method: "PATCH",
    pattern: "/api/skills/:id",
    handler: (req) => {
      const b = (req.body ?? {}) as { enabled?: boolean };
      const s = SKILLS.find((x) => x.skill_id === req.params.id) ?? SKILLS[0];
      return json({ ...s, enabled: b.enabled ?? s.enabled });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/skills/:id",
    handler: () => json({ ok: true }, 204),
  },
  {
    method: "GET",
    pattern: "/api/skills/:id/body",
    handler: () => json({ body: "# Demo skill\n\nIllustrative skill body." }),
  },
  {
    method: "POST",
    pattern: "/api/skills/install",
    handler: () => json({ ok: true, skill_id: "demo-skill" }),
  },

  // --- Report templates ----------------------------------------------------
  {
    method: "GET",
    pattern: "/api/report-templates",
    handler: () => json({ items: REPORT_TEMPLATES }),
  },
  {
    method: "GET",
    pattern: "/api/report-templates/:id",
    handler: (req) => {
      const t = REPORT_TEMPLATES.find((x) => x.id === req.params.id);
      return t ? json(t) : notFound();
    },
  },
  {
    method: "POST",
    pattern: "/api/report-templates",
    handler: (req) => {
      const b = (req.body ?? {}) as { name?: string };
      return json({
        id: "tmpl-demo",
        name: b.name ?? "Demo template",
        template_spec: {},
        source_markdown: null,
        created_at: DEMO_NOW_ISO,
        updated_at: DEMO_NOW_ISO,
      });
    },
  },
  {
    method: "PUT",
    pattern: "/api/report-templates/:id",
    handler: (req) => {
      const b = (req.body ?? {}) as { name?: string };
      return json({
        id: req.params.id,
        name: b.name ?? "Demo template",
        template_spec: {},
        source_markdown: null,
        created_at: DEMO_NOW_ISO,
        updated_at: DEMO_NOW_ISO,
      });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/report-templates/:id",
    handler: () => json({ ok: true }, 204),
  },

  // --- Guardrail activity --------------------------------------------------
  {
    method: "GET",
    pattern: "/api/admin/guardrail-events",
    handler: () => json({ items: GUARDRAIL_EVENTS }),
  },
  {
    method: "DELETE",
    pattern: "/api/admin/guardrail-events",
    handler: () => json({ deleted: 0 }),
  },

  // --- Capabilities (engine manifest) --------------------------------------
  {
    method: "GET",
    pattern: "/api/capabilities",
    handler: () =>
      json({
        engine_version: "report_v3",
        dev_mode: false,
        supported: [
          { id: "web_search_native", summary: "Native model web search." },
          { id: "tool_use", summary: "Single-model tool-use loop." },
        ],
        unsupported: [],
      }),
  },

  // --- Cache admin ---------------------------------------------------------
  {
    method: "GET",
    pattern: "/api/cache/stats",
    handler: () => json({ total_entries: 128, total_bytes: 4_718_592 }),
  },
  {
    method: "DELETE",
    pattern: "/api/cache/documents",
    handler: () => json({ deleted: 0 }),
  },

  // --- Account: active sessions --------------------------------------------
  {
    method: "GET",
    pattern: "/api/auth/sessions",
    handler: () => json({ sessions: AUTH_SESSIONS }),
  },
  {
    method: "DELETE",
    pattern: "/api/auth/sessions/:id",
    handler: () => json({ ok: true }, 204),
  },
  {
    method: "POST",
    pattern: "/api/auth/logout-all",
    handler: () => json(null),
  },
  {
    method: "POST",
    pattern: "/api/auth/change-password",
    handler: () => json(null),
  },
]);
