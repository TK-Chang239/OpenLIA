# Settings de-faking + broken tabs — design

Date: 2026-08-18. Approved by TK.

Source: settings-functionality audit (this session). Every control on the Settings
and Memory pages was traced UI -> API -> DB -> downstream consumer. Six fixes below;
everything else found in the audit is explicitly out of scope.

## 1. Theme radio becomes real (frontend only)

- `useTheme` supports `'system' | 'light' | 'dark'`. `system` resolves via
  `matchMedia('(prefers-color-scheme: dark)')` with a live change listener.
  localStorage `openlia:theme` stores the 3-state value (fast-boot cache).
- Server pref is source of truth: after auth, one `GET /settings/prefs` syncs
  `prefs.theme` into `useTheme`. GeneralSection applies the chosen theme
  immediately on save. TopBar `ThemeToggle` writes through to
  `PATCH /settings/prefs` so the two controls never diverge.

## 2. In-app notifications toggle becomes real (server only)

- Notification creation is gated on `user_prefs.notify_inapp` in one shared
  helper used by every insert path (`scheduler/executors/base.py`,
  `services/pt_runner.py`, `eu_v2_batch_service.py`).
- Toggle off = no new notifications created. Existing rows and the SSE stream
  are untouched.

## 3. Email notifications toggle removed (frontend only)

- Toggle + "Requires SMTP setup by an admin" hint deleted from GeneralSection;
  `notify_email` dropped from the PATCH payload. DB column and API field stay.

## 4. Report output language becomes the global default (server)

- Resolution rule: per-department language if explicitly set, else
  `user_prefs.report_language`, else `en`.
- Shared resolver: `services/user_prefs.resolve_report_language`. Mechanics
  chosen at implementation (no migration needed):
  - v3: `StartV3Payload.language` is now optional; omitted -> resolver. The
    v3 page also seeds its language pill from the global pref on first visit
    (before any localStorage settings exist).
  - EU v2: a user with no `eu_v2_settings` row (never saved the form) gets
    the resolver default from `get_settings`; a saved row is explicit.
  - MB: `ScheduleIn.language` / `RunStartIn.language` are now optional;
    omitted -> resolver at creation time (schedule config is a snapshot,
    like model/template).
  - `both` (bilingual) is only understood by the legacy report runner; the
    resolver clamps it to `en` for the modern engines.

## 5. Broken tabs

- `SettingsShell`: `cache` and `guardrails` tabs marked adminOnly, matching
  their admin-gated routers. Personal mode's single user is admin, so nothing
  is lost there.
- `AdminSkillsSection`: raw `fetch` replaced with a proper API wrapper —
  `res.ok` check, loading state, error state. No white screen on failure.
- `DisclaimerSection`: error message instead of a blank tab on fetch failure.
- `SystemRolesPanel`: "(Unassigned)" calls the existing `deleteSlotDefault`
  instead of silently no-oping.

## Testing

- Server pytest: notify gate on/off; language resolver (dept-set / global-set /
  neither).
- Frontend vitest: `useTheme` system-mode resolution + 3-state persistence;
  settings tests updated for the removed email toggle.

## Out of scope

Env-over-DB API-key precedence, orphan `web_search_providers` table, inert
`rs_user_config` fields, Memory-page UX gaps (refresh/edit/filter/history),
`graph_entities.is_trigger_disabled` writer.
