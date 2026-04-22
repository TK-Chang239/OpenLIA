import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getStatus } from "../api/setup";
import type { WizardStatus } from "../api/setup";

export type WizardState =
  | { state: "loading" }
  | { state: "ready"; status: WizardStatus; refresh: () => Promise<void> }
  | { state: "error"; message: string; refresh: () => Promise<void> };

const WizardCtx = createContext<WizardState | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<WizardState>({ state: "loading" });

  const refresh = useCallback(async () => {
    try {
      const status = await getStatus();
      // `refresh` is captured here — stable because useCallback deps is []
      setValue({ state: "ready", status, refresh: refresh as () => Promise<void> });
    } catch (err) {
      setValue({
        state: "error",
        message: err instanceof Error ? err.message : "Failed to load setup status",
        refresh: refresh as () => Promise<void>,
      });
    }
  // refresh is intentionally omitted — it IS the function being defined
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
