# Connectors as a top-level Settings tab — design

Date: 2026-06-01
Status: Approved (brainstorming), pending implementation plan
Scope owner: frontend settings IA + connector configure UX

## Problem

Connector configuration lives at `/settings/admin/connectors`, buried as an admin-only
sub-tab under the Admin section. After the smart-paste MCP redesign (PR #230) and
secrets-at-rest encryption (PR #231), connectors are a first-class, everyday concern, not
an admin afterthought. The add flow also presents three peer buttons ("Add from catalog",
"Add MCP connector", "Add connector (advanced)") that give equal weight to the legacy paths
and the newest smart-paste path.

This effort promotes Connectors to its own top-level Settings tab and reworks the add flow
so smart-paste is the primary path.

## Goals

1. Surface Connectors as a top-level Settings tab, visible to all users.
2. Make smart-paste the primary, always-visible way to add a connector; demote catalog and
   advanced to secondary paths.
3. Keep all existing connector capability (catalog install, advanced form, edit, validate,
   delete, sync specs, category requirements).
4. No backend changes — the `/connectors` API is unchanged.

## Non-goals

- Admin gating / per-role visibility of the tab — deferred ("all users for now"; revisit
  admin rights later).
- Wiring the connector Edit PATCH endpoint (still a UI-only notice today).
- Key-rotation tooling.
- Moving or changing the Runner specs panel — it stays an admin-only sub-tab.
- Any backend / API / DB change.

## Decisions (locked during brainstorming)

- **Visibility:** the new tab has no `adminOnly` flag — every user sees it. Admin gating is
  future work. Personal mode's single user is already `admin`.
- **Add flow:** smart-paste primary, others secondary (vs. smart-paste-only or keep-all-
  three-equal). Preserves capability while matching the newest implementation.
- **Runner specs:** stays in the Admin section (developer/debug tooling, separate from
  everyday connector configuration).
- **Component home:** rename `ConnectorsAdminPanel` → `ConnectorsSection` and move it from
  `components/settings/admin/` to `components/settings/sections/` (matching its new
  top-level siblings; it is no longer admin-scoped).

## Architecture

### 1. Top-level route + nav item

- `components/settings/SettingsShell.tsx` — add to `ITEMS`:
  `{ to: '/settings/connectors', labelKey: 'settings.tabs.connectors' }`, placed
  immediately after the Models entry. No `adminOnly`.
- `pages/SettingsPage.tsx` — add a top-level
  `<Route path="connectors" element={<ConnectorsSection />} />`; remove the
  `<Route path="connectors" ... />` from inside the nested `admin` block. Update the import
  to the new `sections/ConnectorsSection` path/name.
- `components/settings/sections/AdminSection.tsx` — remove the `connectors` entry from
  `TABS` (Runner specs and the rest stay).

### 2. Rename + relocate the component

- Move `components/settings/admin/ConnectorsAdminPanel.tsx` →
  `components/settings/sections/ConnectorsSection.tsx`. Rename the exported function
  `ConnectorsAdminPanel` → `ConnectorsSection`. No behavior change beyond the add-flow
  rework below. Imports inside the file that reach into `../../connectors/*` and
  `../../../setup/steps/*` adjust for the new directory depth (both `admin/` and `sections/`
  are one level under `settings/`, so relative depths are unchanged).
- Move the test `admin/__tests__/ConnectorsAdminPanel.test.tsx` →
  `sections/__tests__/ConnectorsSection.test.tsx`.

### 3. Rework the add flow (smart-paste primary)

In `ConnectorsSection`:

- The `SmartPasteMcpForm` renders **always-visible** at the top of the tab as the primary
  "Add a connector" card — no button toggle to reach it.
- Remove the `addingMcp` state and its toggle button.
- Beneath the smart-paste card, render a thin secondary row with two text-link buttons:
  **Browse catalog** and **Advanced setup**. These toggle the existing `picking`/`catalog`/
  `chosenTemplate` (`CatalogGrid` + `InstallBuiltinForm`) and `adding` (`AddConnectorForm`)
  flows, which render inline below exactly as today. Keep those states.
- The header keeps the title/subtitle; the three peer action buttons are removed (their
  function moves into the always-on card + secondary links).
- Connector list table, `CategoryRequirementsPanel`, `EditConnectorModal`, and the
  validate / delete / sync-specs / re-resolve handlers are unchanged.

### 4. `SmartPasteMcpForm` — optional Cancel

`setup/steps/SmartPasteMcpForm.tsx`:

- Make the `onCancel` prop optional (`onCancel?: () => void`).
- When `onCancel` is undefined, do not render the Cancel button. The form already resets its
  chip/value/display state on every textarea change, so an always-on instance needs no
  explicit cancel.
- `SmartPasteMcpForm` has exactly one caller today — the panel being renamed to
  `ConnectorsSection`, which will stop passing `onCancel`. (The setup wizard `ConnectorsStep`
  uses `AddConnectorForm`, not this form.) The optional prop keeps the signature
  backward-compatible without a behavior change for any other consumer.

### 5. Fix the stale deep-link

- `components/sidebar/DeptDisabledBanner.tsx` — change the `to="/settings/admin/connectors"`
  link to `to="/settings/connectors"`.

### 6. i18n

`frontend/src/i18n/locales/en.json` and `zh-TW.json`:

- Add `settings.tabs.connectors` ("Connectors" / Traditional Chinese equivalent).
- Add keys for the two secondary links, e.g. `settings.connectors.browse_catalog` and
  `settings.connectors.advanced_setup`.
- Remove the now-unused `settings.admin.tab_connectors`.
- The existing `settings.connectors.*` keys (title, subtitle, table columns, actions, edit
  modal, etc.) are reused unchanged.

## Data flow

No data-flow change. The tab still calls `listConnectors` / `createConnector` /
`validateConnector` / `deleteConnector` / `syncTemplateSpecs` / `reResolveSpecs` against the
same `/connectors` API and refreshes department health the same way.

## Error handling

Unchanged — the existing per-action error banner and the smart-paste form's own error
surface are reused.

## Testing

- `SettingsPage.test.tsx` / `SettingsShell.test.tsx` — assert a top-level **Connectors**
  nav item and that `/settings/connectors` renders `ConnectorsSection`; assert the Admin
  section no longer lists a Connectors sub-tab.
- `ConnectorsSection.test.tsx` (renamed) — the smart-paste paste box is present without any
  "Add MCP connector" toggle; **Browse catalog** and **Advanced setup** secondary links
  reveal the catalog and advanced forms; list/validate/delete still work.
- `SmartPasteMcpForm` test — when rendered without `onCancel`, no Cancel button appears;
  when rendered with it, Cancel appears and fires (preserves existing behavior).
- `DeptDisabledBanner` test (if present) — link points at `/settings/connectors`.

## Open questions

- Exact sidebar position: after Models is the chosen default; trivially adjustable.
- zh-TW wording for "Connectors" / "Browse catalog" / "Advanced setup" — settle the exact
  translations in the plan.
