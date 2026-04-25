import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getStatus } from "../api/setup";
import type { WizardStatus } from "../api/setup";

export type WizardState =
  | { state: "loading" }
  | {
      state: "ready";
      status: WizardStatus;
      refresh: () => Promise<void>;
      goBack: () => void;
      viewStep: string | null;
    }
  | { state: "error"; message: string; refresh: () => Promise<void> };

const WizardCtx = createContext<WizardState | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<WizardState>({ state: "loading" });

  // `viewStep` overrides the server's `current_step` for the Back button —
  // it lets the user revisit a previously-completed step without losing
  // their forward state. `null` means "follow server".
  const goBack = useCallback(() => {
    setValue((prev) => {
      if (prev.state !== "ready") return prev;
      const completed = prev.status.completed_steps;
      const current = prev.viewStep ?? prev.status.current_step;
      const idx = completed.indexOf(current);
      // If the current step is completed, go to its predecessor; otherwise
      // jump to the last completed step.
      const target =
        idx > 0 ? completed[idx - 1] : completed.length > 0 ? completed[completed.length - 1] : null;
      if (!target) return prev;
      return { ...prev, viewStep: target };
    });
  }, []);

  const refresh = useCallback(async () => {
    try {
      const status = await getStatus();
      // Forward navigation clears the back-override so the next step renders
      // as the server reports it.
      setValue({
        state: "ready",
        status,
        refresh: refresh as () => Promise<void>,
        goBack,
        viewStep: null,
      });
    } catch (err) {
      setValue({
        state: "error",
        message: err instanceof Error ? err.message : "Failed to load setup status",
        refresh: refresh as () => Promise<void>,
      });
    }
    // refresh is intentionally omitted — it IS the function being defined
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goBack]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const memo = useMemo(() => value, [value]);
  return <WizardCtx.Provider value={memo}>{children}</WizardCtx.Provider>;
}

export function useWizard(): WizardState {
  const ctx = useContext(WizardCtx);
  if (!ctx) throw new Error("useWizard must be used inside WizardProvider");
  return ctx;
}
