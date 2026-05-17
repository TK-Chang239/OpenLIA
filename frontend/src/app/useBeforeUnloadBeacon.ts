import { useEffect } from "react";

export function useBeforeUnloadBeacon(): void {
  useEffect(() => {
    function onBeforeUnload() {
      try {
        navigator.sendBeacon("/notifications/presence-close");
      } catch {
        // best-effort; the auto-cancel sweep still fires after grace
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);
}
