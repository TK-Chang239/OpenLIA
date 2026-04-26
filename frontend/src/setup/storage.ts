// Single source of truth for wizard sessionStorage: keys, the field-persistence
// hook, and the global clear that runs after /setup/finish.
//
// Steps must use useWizardField rather than touching sessionStorage directly.
// Secrets (passwords, API keys the user has not yet saved) are kept out by
// not passing them into the hook — the persistence boundary is explicit at
// the call site, not magic inside the hook.

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

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

function readRaw(key: WizardStorageKey): unknown {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return undefined;
    return JSON.parse(raw) as unknown;
  } catch {
    return undefined;
  }
}

function writeRaw(key: WizardStorageKey, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota / disabled storage */
  }
}

// useState that auto-loads from and saves to sessionStorage under `key`.
// `parse` validates/sanitizes the raw stored value; if it throws or the slot
// is empty, `defaultValue` is used. Without `parse`, the stored value must
// already match T (use only for primitives or trusted-shape objects).
export function useWizardField<T>(
  key: WizardStorageKey,
  defaultValue: T,
  parse?: (raw: unknown) => T,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    const raw = readRaw(key);
    if (raw === undefined) return defaultValue;
    if (!parse) return raw as T;
    try {
      return parse(raw);
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    writeRaw(key, value);
  }, [key, value]);

  return [value, setValue];
}
