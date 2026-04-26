// Single source of truth for wizard sessionStorage keys.
//
// Each step that persists form fields imports its key from here rather than
// defining a local constant. clearAllWizardStorage() runs once on successful
// /setup/finish so the tab is clean for any future re-entry.

export const WIZARD_STORAGE_KEYS = [
  "openlia.wizard.identity",
  "openlia.wizard.admin",
  "openlia.wizard.access_control",
  "openlia.wizard.models",
] as const;

export type WizardStorageKey = (typeof WIZARD_STORAGE_KEYS)[number];

export function clearAllWizardStorage(): void {
  for (const key of WIZARD_STORAGE_KEYS) {
    try {
      sessionStorage.removeItem(key);
    } catch {
      /* ignore quota / disabled storage */
    }
  }
}
