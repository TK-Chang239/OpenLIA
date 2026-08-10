// Bootstrap fixtures: the calls the app makes on first load to decide auth
// mode, setup completion, department health, and the safety disclaimer. These
// answers land the demo straight on Home in no-auth personal mode with every
// department enabled.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO } from "../clock";

export const DISCLAIMER_VERSION = "demo-1";

// Every department shows as active so nothing is banner-disabled in the demo.
const DEPARTMENT_IDS = [
  "secretary",
  "equity_research",
  "earnings_update",
  "morning_briefing",
  "retail_sentiment",
  "macro_research",
  "panic_thermometer",
];

register([
  // Auth: 404 => personal mode (single local user, no login gate).
  {
    method: "GET",
    pattern: "/api/auth/session",
    handler: () => notFound("personal_mode"),
  },

  // Setup wizard: already completed so SetupGate lets the app render.
  {
    method: "GET",
    pattern: "/api/setup/status",
    handler: () =>
      json({
        mode: "personal",
        wizard_completed: true,
        current_step: "done",
        completed_steps: [
          "mode",
          "identity",
          "models",
          "connectors",
          "review",
        ],
        env_overrides: {},
      }),
  },

  // Department health: all active.
  {
    method: "GET",
    pattern: "/api/dept-health",
    handler: () =>
      json(
        DEPARTMENT_IDS.map((id) => ({
          department_id: id,
          status: "active",
          reason: null,
          missing_categories: [],
          required_categories: [],
          optional_categories: [],
          satisfied_categories: [],
          required_any_of: [],
          unsatisfied_any_of: [],
        })),
      ),
  },
  {
    method: "POST",
    pattern: "/api/dept-health/refresh",
    handler: () =>
      json(
        DEPARTMENT_IDS.map((id) => ({
          department_id: id,
          status: "active",
          reason: null,
          missing_categories: [],
        })),
      ),
  },

  // Safety disclaimer.
  {
    method: "GET",
    pattern: "/api/disclaimer",
    handler: () =>
      json({
        version: DISCLAIMER_VERSION,
        text:
          "This is a demonstration of OpenLIA populated with illustrative sample data. " +
          "Nothing here is real market data, a real report, or investment advice.",
      }),
  },
  {
    method: "GET",
    pattern: "/api/disclaimer/status",
    handler: () =>
      json({
        current_version: DISCLAIMER_VERSION,
        accepted: true,
        accepted_version: DISCLAIMER_VERSION,
      }),
  },
  {
    method: "POST",
    pattern: "/api/disclaimer/accept",
    handler: () => json({ ok: true }),
  },

  // Timezone / unload beacons the app fires on boot — accept and ignore.
  {
    method: "POST",
    pattern: "/api/prefs/timezone",
    handler: () => json({ ok: true }),
  },
  {
    method: "GET",
    pattern: "/api/notifications/unread",
    handler: () => json({ total: 0, by_department: {} }),
  },
  {
    method: "POST",
    pattern: "/api/notifications/read",
    handler: () => json({ marked_read: 0 }),
  },
]);

export { DEMO_NOW_ISO };
