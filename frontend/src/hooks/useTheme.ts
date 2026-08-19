import { useSyncExternalStore } from "react";

/** What the user picked. `system` follows the OS preference live. */
export type ThemeSetting = "system" | "light" | "dark";
/** What is actually painted on `<html data-theme>`. */
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "openlia:theme";

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

function readStored(): ThemeSetting {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light" || stored === "system") return stored;
  return "system";
}

export function resolveTheme(setting: ThemeSetting): ResolvedTheme {
  return setting === "system" ? (systemPrefersDark() ? "dark" : "light") : setting;
}

// Module-level store so every useTheme() consumer (TopBar toggle, Settings
// radio) sees the same value instead of holding divergent copies.
let setting: ThemeSetting = readStored();
const listeners = new Set<() => void>();

function apply(): void {
  document.documentElement.setAttribute("data-theme", resolveTheme(setting));
}

function notify(): void {
  for (const l of listeners) l();
}

/**
 * Set + persist the theme locally (localStorage cache). The server pref
 * (`user_prefs.theme`) is the source of truth; callers that change the theme
 * on the user's behalf also PATCH /api/settings/prefs themselves.
 */
export function setThemeSetting(next: ThemeSetting): void {
  setting = next;
  localStorage.setItem(STORAGE_KEY, next);
  apply();
  notify();
}

if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
  try {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", () => {
        if (setting === "system") {
          apply();
          notify();
        }
      });
  } catch {
    // matchMedia without addEventListener (old engines/jsdom): system mode
    // then only re-resolves on reload.
  }
}

// Paint the stored theme at import time so the app never flashes the wrong one.
apply();

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

// Snapshot encodes setting + resolution so an OS-preference flip in `system`
// mode re-renders subscribers even though the setting itself is unchanged.
function getSnapshot(): string {
  return `${setting}:${resolveTheme(setting)}`;
}

export function useTheme(): {
  theme: ThemeSetting;
  resolved: ResolvedTheme;
  setTheme: (t: ThemeSetting) => void;
} {
  const snap = useSyncExternalStore(subscribe, getSnapshot);
  const [theme, resolved] = snap.split(":") as [ThemeSetting, ResolvedTheme];
  return { theme, resolved, setTheme: setThemeSetting };
}
