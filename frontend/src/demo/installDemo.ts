// Entry point for demo mode. Installs the fetch + EventSource shims, seeds the
// personal-mode disclaimer acceptance so the app boots straight to Home, and
// mounts the demo badge. Imported dynamically from main.tsx only when
// VITE_DEMO_MODE is set, so none of this ships in the normal build.

import { demoFetch, setOriginalFetch } from "./fetchRouter";
import { DemoEventSource } from "./DemoEventSource";
import { mountDemoBadge } from "./DemoBadge";
import { DISCLAIMER_VERSION } from "./data/bootstrap";
import { DEMO_NOW_ISO } from "./clock";
// Side-effect import: every data module registers its routes/streams here.
import "./data";

let installed = false;

export function installDemo(): void {
  if (installed) return;
  installed = true;

  setOriginalFetch(globalThis.fetch.bind(globalThis));
  globalThis.fetch = demoFetch;
  globalThis.EventSource = DemoEventSource as unknown as typeof EventSource;

  // Personal-mode disclaimer acceptance lives in localStorage; pre-seed it to
  // the demo disclaimer version so the entry modal doesn't gate the click-through.
  try {
    localStorage.setItem(
      "lia_disclaimer_accepted",
      JSON.stringify({ version: DISCLAIMER_VERSION, accepted_at: DEMO_NOW_ISO }),
    );
  } catch {
    // Private-mode / storage-disabled: the disclaimer endpoint will 404 and the
    // gate unblocks anyway.
  }

  if (typeof document !== "undefined") {
    if (document.body) mountDemoBadge();
    else document.addEventListener("DOMContentLoaded", mountDemoBadge, { once: true });
  }
}
