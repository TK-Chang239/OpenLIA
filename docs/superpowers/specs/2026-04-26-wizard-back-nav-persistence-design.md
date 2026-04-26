# Wizard Back-Navigation Persistence

**Date:** 2026-04-26
**Author:** TK Chang
**Status:** Approved — proceeding to implementation

## Problem

In the OpenLIA setup wizard, going back to a previously-completed step shows a blank form. The user expects every field to restore exactly as it was when they clicked Next.

The current code already writes form values to `sessionStorage` on every keystroke, but each step *clears* its key after a successful Next. So the first time the user revisits a step the data is gone. The previous fix only solved the in-step refresh case, not the back-navigation case the user actually reported.

## Goal

When the user clicks Next on any wizard step:
- The data they entered stays in `sessionStorage` for the lifetime of the browser tab.
- Returning to that step (via Back, page refresh, or hard reload) restores every field exactly as it was.

When the wizard finishes (successful `POST /setup/finish`):
- All wizard `sessionStorage` keys are cleared so the tab is clean for any re-entry.

## Sensitive-field policy (option C)

Persist API keys but not the admin password.

- **Persisted:** display name, admin email, admin display name, signup policy, allowed domains, bind host/port, model API keys (already persisted today), tier selections, model picks.
- **Not persisted:** admin password, confirm-password. Those two fields stay in component state only and are blank when the user revisits `AdminAccountStep` after advancing past it. Everything else on that step still restores.

## Approach (option 1)

Smallest-delta variant of what the code already does. Persist on every keystroke (current pattern). Stop deleting the entry when Next succeeds. Add one global clear that runs from `ReviewStep` after `POST /setup/finish` returns.

Rejected alternatives:
- *Snapshot-on-Next.* Cleaner mental model, but a mid-typing refresh would lose state and the user-visible behavior is otherwise identical. Not worth the rework.
- *Server-backed restore.* "More correct" since the DB already holds these fields, but doubles the surface area: new GET endpoints per step, new fetch-on-mount logic per step, and we still need component-level handling for the password fields. Out of scope.

## Files affected

```
frontend/src/setup/storage.ts                              (new)
frontend/src/setup/steps/IdentityStep.tsx                  (drop post-Next clear)
frontend/src/setup/steps/AdminAccountStep.tsx              (drop post-Next clear)
frontend/src/setup/steps/AccessControlStep.tsx             (drop post-Next clear)
frontend/src/setup/steps/ModelsStep.tsx                    (drop post-save clear)
frontend/src/setup/steps/ReviewStep.tsx                    (call clearAllWizardStorage after finish())
frontend/src/setup/steps/IdentityStep.test.tsx             (new restoration test)
frontend/src/setup/steps/AdminAccountStep.test.tsx         (extend with restoration test)
frontend/src/setup/steps/AccessControlStep.test.tsx        (extend with restoration test)
frontend/src/setup/steps/ModelsStep.test.tsx               (extend with restoration test, if file exists)
```

Out of scope:
- `ModeStep` — no editable fields beyond a single radio, already reflects server-stored mode.
- `ProvidersStep` — DB-backed; revisiting refetches via `listProviders()`.
- `WizardContext` — back-navigation logic already correct; only the steps' clearing was wrong.

## New module: `storage.ts`

Single source of truth for wizard storage keys.

```ts
// frontend/src/setup/storage.ts
export const WIZARD_STORAGE_KEYS = [
  "openlia.wizard.identity",
  "openlia.wizard.admin",
  "openlia.wizard.access_control",
  "openlia.wizard.models",
] as const;

export function clearAllWizardStorage(): void {
  for (const key of WIZARD_STORAGE_KEYS) {
    try {
      sessionStorage.removeItem(key);
    } catch {
      /* ignore quota / disabled storage */
    }
  }
}
```

Each step file imports its key from this module instead of defining a local `STORAGE_KEY` constant, so the canonical list lives in one place. (This is a small refactor; not strictly required for the fix, but it keeps the cleanup correct if a new step adds a key later.)

## Wizard-finish hook

In `ReviewStep.tsx`, after `await finish()` succeeds and before the redirect:

```ts
const { redirect } = await finish();
clearAllWizardStorage();
window.location.href = redirect;
```

`finish()` is the only place where the wizard transitions from "in progress" to "done" from the user's perspective, so it's the right place to clear. If the call fails, we leave storage intact so the user can retry without re-entering data.

## Tests

For each of `IdentityStep`, `AdminAccountStep`, `AccessControlStep`, and `ModelsStep`:

1. Render the step.
2. Type into each field.
3. Click Next; mock the API to succeed.
4. Re-render the same step (simulating back-navigation by tearing down and rendering again in the same test).
5. Assert each field shows the value typed in step 2.
6. For `AdminAccountStep` specifically, assert the password and confirm-password inputs are **blank** after re-render.

`setupTests.ts` already calls `sessionStorage.clear()` in `afterEach`, so tests stay isolated.

Optionally one integration-style test that asserts `clearAllWizardStorage()` is invoked after `finish()` resolves, by spying on `sessionStorage.removeItem`. Not strictly required if the per-step tests already cover the persistence behavior.

## Risks & considerations

- **Tab sharing.** `sessionStorage` is per-tab, so opening a second tab to the wizard starts fresh. Acceptable for a setup wizard.
- **Password security.** Plain-text persistence of API keys in `sessionStorage` is the same risk profile we already accept for the Models step. The admin password is the one field most likely to be reused elsewhere; excluding it (option C) is the deliberate trade-off.
- **Finish failure.** If `finish()` throws, storage is preserved and the user can retry. Once the redirect lands on the post-wizard URL, the next time the user opens the wizard route the new tab starts with empty `sessionStorage` anyway.

## Verification

- `npm run lint` — clean.
- `npm test -- --run` — all wizard tests pass, including new restoration tests.
- `uv run pytest packages/server/tests/test_routes/test_setup_routes.py` — no regression (this fix is frontend-only but the backend tests are cheap to re-run).
- Manual smoke in a real browser: complete each step, click Back, confirm the form restores; on `AdminAccountStep` confirm the password field is blank while email and display name are populated.
