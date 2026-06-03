/**
 * Persistence for the Run Now config. The form remembers the user's previous
 * Run Now submission per browser under `mb.run_now.last_config` and prefills
 * from it; first use falls back to the library defaults (mb_default template,
 * backend-default model, no connectors). "Previous run" = the last config
 * actually submitted via Run Now — scheduled runs keep their own bindings.
 */
import type { MbConfigDraft } from "./MbConfigFields";

export const RUN_NOW_LS_KEY = "mb.run_now.last_config";

export function libraryDefaultDraft(): MbConfigDraft {
  return {
    template_id: "mb_default",
    instructions_id: null,
    provider_ids: [],
    web_search: false,
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
  };
}

export function loadRunNowDraft(): MbConfigDraft {
  if (typeof window === "undefined") return libraryDefaultDraft();
  try {
    const raw = window.localStorage.getItem(RUN_NOW_LS_KEY);
    if (!raw) return libraryDefaultDraft();
    const parsed = JSON.parse(raw) as Partial<MbConfigDraft>;
    return { ...libraryDefaultDraft(), ...parsed };
  } catch {
    return libraryDefaultDraft();
  }
}

export function saveRunNowDraft(draft: MbConfigDraft): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(RUN_NOW_LS_KEY, JSON.stringify(draft));
  } catch {
    /* localStorage may be disabled */
  }
}
