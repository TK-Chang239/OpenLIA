# Connectors Settings Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote connector configuration from an admin-only sub-tab to a top-level Settings tab visible to all users, with smart-paste as the primary add path.

**Architecture:** Frontend-only change. The admin `ConnectorsAdminPanel` is reworked in place (smart-paste form always-visible; catalog + advanced demoted to secondary links), then relocated/renamed to a top-level `ConnectorsSection` and wired into `SettingsShell` nav + `SettingsPage` routes. No backend, API, or DB change — the same `/connectors` endpoints are used.

**Tech Stack:** React + TypeScript + Vite, react-router-dom, react-i18next, Vitest + @testing-library/react.

---

## File Structure

- `frontend/src/setup/steps/SmartPasteMcpForm.tsx` — make `onCancel` optional so the form can render always-on without a Cancel button.
- `frontend/src/i18n/locales/en.json`, `zh-TW.json` — add `settings.tabs.connectors` + `settings.connectors.other_ways`; later remove `settings.admin.tab_connectors`.
- `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx` → `frontend/src/components/settings/sections/ConnectorsSection.tsx` — reworked add flow, then moved + renamed.
- `frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx` → `frontend/src/components/settings/sections/__tests__/ConnectorsSection.test.tsx`.
- `frontend/src/pages/SettingsPage.tsx` — top-level `connectors` route; drop nested admin route.
- `frontend/src/components/settings/SettingsShell.tsx` — add Connectors nav item.
- `frontend/src/components/settings/sections/AdminSection.tsx` — drop Connectors sub-tab.
- `frontend/src/components/sidebar/DeptDisabledBanner.tsx` — fix deep link to `/settings/connectors`.
- Test updates: `SettingsShell.test.tsx`, `SettingsPage.test.tsx`, `DeptDisabledBanner.test.tsx`.

Each task leaves the app building and all tests green.

---

### Task 1: `SmartPasteMcpForm` — optional `onCancel`

**Files:**
- Modify: `frontend/src/setup/steps/SmartPasteMcpForm.tsx`
- Test: `frontend/src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Append this test inside the existing `describe("SmartPasteMcpForm", ...)` block in `frontend/src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`:

```tsx
  it("omits the Cancel button when onCancel is not provided", () => {
    render(<SmartPasteMcpForm onCreated={() => {}} />);
    expect(screen.queryByRole("button", { name: /^cancel$/i })).toBeNull();
    // The primary submit button is still present.
    expect(
      screen.getByRole("button", { name: /validate & add/i }),
    ).toBeInTheDocument();
  });

  it("renders the Cancel button when onCancel is provided", () => {
    render(<SmartPasteMcpForm onCancel={() => {}} onCreated={() => {}} />);
    expect(
      screen.getByRole("button", { name: /^cancel$/i }),
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`
Expected: the "omits the Cancel button" test FAILS — TypeScript/runtime currently requires `onCancel` and always renders Cancel. (It may surface as a type error on `<SmartPasteMcpForm onCreated=... />` missing `onCancel`.)

- [ ] **Step 3: Make `onCancel` optional**

In `frontend/src/setup/steps/SmartPasteMcpForm.tsx`, change the `Props` interface:

```tsx
interface Props {
  onCancel?: () => void;
  onCreated: (row: ConnectorRow) => void;
}
```

And update the destructure to default it (so the unused-var lint is satisfied and the value is plain):

```tsx
export function SmartPasteMcpForm({ onCancel, onCreated }: Props) {
```

Then wrap the Cancel button (currently unconditional) so it only renders when `onCancel` is set. Replace this block:

```tsx
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
          >
            Cancel
          </button>
```

with:

```tsx
          {onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
            >
              Cancel
            </button>
          ) : null}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`
Expected: PASS (all tests, including the two new ones and the existing five).

- [ ] **Step 5: Commit**

```bash
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/setup/steps/SmartPasteMcpForm.tsx frontend/src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx
git commit -m "feat(connectors): make SmartPasteMcpForm onCancel optional"
```

---

### Task 2: i18n — add the Connectors tab + secondary-link labels

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

No test step — these keys are exercised by the component tests in later tasks.

- [ ] **Step 1: Add `settings.tabs.connectors` (en)**

In `frontend/src/i18n/locales/en.json`, find the `settings.tabs` block and insert a `connectors` entry after `models`. Replace:

```json
    "models": "Models",
    "timezone": "Timezone & Memory",
```

with:

```json
    "models": "Models",
    "connectors": "Connectors",
    "timezone": "Timezone & Memory",
```

- [ ] **Step 2: Add `settings.connectors.other_ways` (en)**

In the same file, find the `settings.connectors` block and insert an `other_ways` entry next to the existing add labels. Replace:

```json
    "add_from_catalog": "Add from catalog",
```

with:

```json
    "other_ways": "Other ways to add:",
    "add_from_catalog": "Add from catalog",
```

- [ ] **Step 3: Add the same keys (zh-TW)**

In `frontend/src/i18n/locales/zh-TW.json`, replace:

```json
    "models": "模型",
    "timezone": "時區與記憶",
```

with:

```json
    "models": "模型",
    "connectors": "資料連接器",
    "timezone": "時區與記憶",
```

Then replace:

```json
    "add_from_catalog": "從目錄新增",
```

with:

```json
    "other_ways": "其他新增方式：",
    "add_from_catalog": "從目錄新增",
```

- [ ] **Step 4: Verify both JSON files still parse**

Run: `cd /Users/tkchang/Projects/OpenLIA && python3 -c "import json; json.load(open('frontend/src/i18n/locales/en.json')); json.load(open('frontend/src/i18n/locales/zh-TW.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "i18n(connectors): add Connectors tab + secondary-link labels"
```

---

### Task 3: Rework the add flow in `ConnectorsAdminPanel` (in place)

Smart-paste becomes an always-visible primary card; catalog + advanced become secondary links. The "Add MCP connector" toggle button and its `addingMcp` state are removed. (The file is renamed in Task 4 — keep it as `ConnectorsAdminPanel` for now.)

**Files:**
- Modify: `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx`
- Test: `frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

Append this test inside the existing `describe("ConnectorsAdminPanel", ...)` block in `frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx`:

```tsx
  it("shows the smart-paste box as the always-visible primary add path", async () => {
    render(<ConnectorsAdminPanel />);
    // Smart-paste textarea is present on mount, with no toggle button to reveal it.
    expect(
      await screen.findByLabelText(/paste a url or command/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add mcp connector/i }),
    ).toBeNull();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx`
Expected: FAIL — the smart-paste box is only rendered behind the `addingMcp` toggle today, so `findByLabelText(/paste a url or command/i)` times out.

- [ ] **Step 3: Swap `addingMcp` state for a `formNonce`**

In `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx`, replace this state line:

```tsx
  const [addingMcp, setAddingMcp] = useState(false);
```

with:

```tsx
  const [formNonce, setFormNonce] = useState(0);
```

- [ ] **Step 4: Replace the header button cluster with the always-on form + secondary links**

Replace the entire `<header>...</header>` block (the one containing the three add buttons):

```tsx
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-text-primary">{t('settings.connectors.title')}</h2>
          <p className="mt-1 text-sm text-text-secondary">
            {t('settings.connectors.subtitle')}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={async () => {
              if (catalog === null) setCatalog(await listBuiltinTemplates());
              setPicking(true);
            }}
            className="rounded bg-accent-primary px-4 py-2 text-sm text-text-on-accent"
          >
            {t('settings.connectors.add_from_catalog')}
          </button>
          <button
            type="button"
            onClick={() => { setAddingMcp(true); setAdding(false); }}
            className="rounded border border-border-subtle px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
          >
            {t('settings.connectors.add_mcp')}
          </button>
          <button
            type="button"
            onClick={() => { setAdding(true); setAddingMcp(false); }}
            className="rounded border border-border-subtle px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
          >
            {t('settings.connectors.add_advanced')}
          </button>
        </div>
      </header>
```

with:

```tsx
      <header>
        <h2 className="text-base font-semibold text-text-primary">{t('settings.connectors.title')}</h2>
        <p className="mt-1 text-sm text-text-secondary">
          {t('settings.connectors.subtitle')}
        </p>
      </header>

      <SmartPasteMcpForm
        key={formNonce}
        onCreated={() => {
          setFormNonce((n) => n + 1);
          void refresh();
        }}
      />

      <div className="flex items-center gap-3 text-sm">
        <span className="text-text-secondary">{t('settings.connectors.other_ways')}</span>
        <button
          type="button"
          onClick={async () => {
            if (catalog === null) setCatalog(await listBuiltinTemplates());
            setPicking(true);
          }}
          className="text-accent-primary hover:underline"
        >
          {t('settings.connectors.add_from_catalog')}
        </button>
        <span className="text-text-secondary">·</span>
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="text-accent-primary hover:underline"
        >
          {t('settings.connectors.add_advanced')}
        </button>
      </div>
```

- [ ] **Step 5: Remove the old bottom-of-component `addingMcp` form block**

Delete this block (the conditional smart-paste form that used to render at the bottom):

```tsx
      {addingMcp && (
        <SmartPasteMcpForm
          onCancel={() => setAddingMcp(false)}
          onCreated={(_row) => {
            setAddingMcp(false);
            void refresh();
          }}
        />
      )}

```

Leave the `{adding && (<AddConnectorForm ... />)}`, `{picking && (<CatalogGrid ... />)}`, and `{chosenTemplate && (<InstallBuiltinForm ... />)}` blocks unchanged.

- [ ] **Step 6: Run the panel tests to verify they pass**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx`
Expected: PASS — the new test plus all existing ones (rows, validate, delete, edit modal, empty-state, catalog grid, install form).

- [ ] **Step 7: Commit**

```bash
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx
git commit -m "feat(connectors): smart-paste primary, catalog/advanced as secondary links"
```

---

### Task 4: Relocate + rename to `ConnectorsSection` and wire the top-level tab

**Files:**
- Move: `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx` → `frontend/src/components/settings/sections/ConnectorsSection.tsx`
- Move: `frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx` → `frontend/src/components/settings/sections/__tests__/ConnectorsSection.test.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/components/settings/SettingsShell.tsx`
- Modify: `frontend/src/components/settings/sections/AdminSection.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `zh-TW.json` (remove orphaned key)
- Test: `frontend/src/components/settings/__tests__/SettingsShell.test.tsx`, `frontend/src/pages/__tests__/SettingsPage.test.tsx`

- [ ] **Step 1: `git mv` the component and its test**

```bash
cd /Users/tkchang/Projects/OpenLIA
git mv frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx frontend/src/components/settings/sections/ConnectorsSection.tsx
git mv frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx frontend/src/components/settings/sections/__tests__/ConnectorsSection.test.tsx
```

(The relative import depths are identical — `admin/` and `sections/` are both one level under `settings/` — so the imports inside the moved files need no path edits.)

- [ ] **Step 2: Rename the exported component**

In `frontend/src/components/settings/sections/ConnectorsSection.tsx`, rename the export:

```tsx
export function ConnectorsSection(): JSX.Element {
```

(It was `export function ConnectorsAdminPanel(): JSX.Element {`. The internal `EditConnectorModal` helper keeps its name.)

- [ ] **Step 3: Update the moved test's references**

In `frontend/src/components/settings/sections/__tests__/ConnectorsSection.test.tsx`, change the import and every `<ConnectorsAdminPanel />` usage and the `describe` title to `ConnectorsSection`:
- Import: `import { ConnectorsSection } from "../ConnectorsSection";`
- `describe("ConnectorsSection", () => {`
- Replace all `render(<ConnectorsAdminPanel />)` with `render(<ConnectorsSection />)`.

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/components/settings/sections/__tests__/ConnectorsSection.test.tsx`
Expected: PASS (same suite as Task 3, now under the new name).

- [ ] **Step 4: Wire the top-level route in `SettingsPage`**

In `frontend/src/pages/SettingsPage.tsx`:

Change the import (line ~17):

```tsx
import { ConnectorsSection } from '../components/settings/sections/ConnectorsSection';
```

Add a top-level route immediately after the `models` route:

```tsx
        <Route path="models" element={<ModelsSection userRole={user.role} />} />
        <Route path="connectors" element={<ConnectorsSection />} />
```

Remove the nested admin route line:

```tsx
            <Route path="connectors" element={<ConnectorsAdminPanel />} />
```

- [ ] **Step 5: Add the nav item in `SettingsShell`**

In `frontend/src/components/settings/SettingsShell.tsx`, add a Connectors entry to `ITEMS` after `models`:

```tsx
  { to: '/settings/models', labelKey: 'settings.tabs.models' },
  { to: '/settings/connectors', labelKey: 'settings.tabs.connectors' },
  { to: '/settings/timezone', labelKey: 'settings.tabs.timezone' },
```

- [ ] **Step 6: Drop the Connectors sub-tab from `AdminSection`**

In `frontend/src/components/settings/sections/AdminSection.tsx`, remove this entry from `TABS`:

```tsx
  { to: 'connectors', labelKey: 'settings.admin.tab_connectors' },
```

- [ ] **Step 7: Remove the orphaned i18n key**

In `frontend/src/i18n/locales/en.json`, delete the line:

```json
    "tab_connectors": "Connectors",
```

In `frontend/src/i18n/locales/zh-TW.json`, delete the line:

```json
    "tab_connectors": "資料連接器",
```

Verify JSON still parses:
Run: `cd /Users/tkchang/Projects/OpenLIA && python3 -c "import json; json.load(open('frontend/src/i18n/locales/en.json')); json.load(open('frontend/src/i18n/locales/zh-TW.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 8: Update `SettingsShell.test.tsx`**

In `frontend/src/components/settings/__tests__/SettingsShell.test.tsx`, add a `connectors` child route to the `renderAt` router and a test asserting the nav link renders for a regular user.

Add to the `children` array (after the `models` entry):

```tsx
          { path: 'connectors', element: <p>connectors body</p> },
```

Add this test inside the `describe('SettingsShell', ...)` block:

```tsx
  it('renders the Connectors nav item for a regular user', () => {
    renderAt('/settings/general');
    expect(
      screen.getByRole('link', { name: /connectors/i }),
    ).toBeInTheDocument();
  });
```

- [ ] **Step 9: Update `SettingsPage.test.tsx`**

In `frontend/src/pages/__tests__/SettingsPage.test.tsx`, mock the new section and assert it renders at its route for a non-admin user.

Add a mock alongside the other `vi.mock(...)` calls:

```tsx
vi.mock('../../components/settings/sections/ConnectorsSection', () => ({
  ConnectorsSection: () => <p>connectors body</p>,
}));
```

Add this test inside `describe('SettingsPage', ...)`:

```tsx
  it('renders Connectors at its top-level route for a non-admin user', async () => {
    vi.spyOn(currentUserModule, 'useCurrentUser').mockReturnValue({
      id: 'u-1',
      email: 'user@example.com',
      display_name: 'User',
      role: 'user',
      must_change_password: false,
    });
    renderAt('/settings/connectors');
    await waitFor(() => screen.getByText('connectors body'));
    expect(screen.getByText('connectors body')).toBeInTheDocument();
  });
```

- [ ] **Step 10: Run the affected suites**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/components/settings/__tests__/SettingsShell.test.tsx src/pages/__tests__/SettingsPage.test.tsx src/components/settings/sections/__tests__/ConnectorsSection.test.tsx`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/components/settings frontend/src/pages/SettingsPage.tsx frontend/src/pages/__tests__/SettingsPage.test.tsx frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "feat(connectors): promote Connectors to a top-level settings tab"
```

---

### Task 5: Fix the department-disabled deep link

**Files:**
- Modify: `frontend/src/components/sidebar/DeptDisabledBanner.tsx`
- Test: `frontend/src/components/sidebar/DeptDisabledBanner.test.tsx`

- [ ] **Step 1: Update the failing test expectation**

In `frontend/src/components/sidebar/DeptDisabledBanner.test.tsx`, change the href assertion:

```tsx
    expect(
      screen.getByRole("link", { name: /settings.*connectors/i }),
    ).toHaveAttribute("href", "/settings/connectors");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/components/sidebar/DeptDisabledBanner.test.tsx`
Expected: FAIL — the link still points at `/settings/admin/connectors`.

- [ ] **Step 3: Update the link target**

In `frontend/src/components/sidebar/DeptDisabledBanner.tsx`, change:

```tsx
      <Link
        to="/settings/connectors"
        className="text-sm font-medium underline hover:no-underline"
      >
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run src/components/sidebar/DeptDisabledBanner.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/tkchang/Projects/OpenLIA
git add frontend/src/components/sidebar/DeptDisabledBanner.tsx frontend/src/components/sidebar/DeptDisabledBanner.test.tsx
git commit -m "fix(connectors): point dept-disabled banner at /settings/connectors"
```

---

### Task 6: Full frontend verification

**Files:** none (verification only)

- [ ] **Step 1: Type-check**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx tsc --noEmit`
Expected: no errors. (Confirms no stale `ConnectorsAdminPanel` import or `onCancel` type regression remains.)

- [ ] **Step 2: Confirm no stale references**

Run: `cd /Users/tkchang/Projects/OpenLIA && grep -rn "ConnectorsAdminPanel\|settings/admin/connectors\|tab_connectors" frontend/src`
Expected: no matches.

- [ ] **Step 3: Run the full frontend test suite**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npx vitest run`
Expected: PASS (no regressions).

- [ ] **Step 4: Production build**

Run: `cd /Users/tkchang/Projects/OpenLIA/frontend && npm run build`
Expected: build succeeds (a pre-existing large-chunk warning is acceptable).

- [ ] **Step 5: Commit (only if any verification produced fixups)**

```bash
cd /Users/tkchang/Projects/OpenLIA
git add -A
git commit -m "chore(connectors): verification fixups"
```

(If nothing changed, skip this commit.)

---

## Self-Review Notes

- **Spec coverage:** top-level tab (Tasks 4–5), all-users visibility (Task 4, no `adminOnly`), smart-paste primary + secondary links (Task 3), capability preserved (catalog/advanced/edit/validate/delete kept), Runner specs untouched (only the `connectors` entry leaves `AdminSection`), stale deep-link fixed (Task 5), i18n (Tasks 2 & 4), `SmartPasteMcpForm` optional Cancel (Task 1). No backend change.
- **Type consistency:** export renamed `ConnectorsAdminPanel` → `ConnectorsSection` consistently across the component, its test, and the `SettingsPage` import. `onCancel?` optional prop matches both call sites (always-on with no `onCancel`; any future caller passing it still works).
- **Build-green ordering:** i18n keys (Task 2) land before the JSX that references them (Task 3); the in-place rework (Task 3) precedes the mechanical move (Task 4) so each commit compiles.
