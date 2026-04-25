import type { JSX, ReactNode } from "react";
import { createContext, useContext, useMemo, useState } from "react";

interface MobileNavContextValue {
  open: boolean;
  setOpen: (next: boolean) => void;
}

const MobileNavContext = createContext<MobileNavContextValue | null>(null);

export function MobileNavProvider({ children }: { children: ReactNode }): JSX.Element {
  const [open, setOpen] = useState(false);
  const value = useMemo(() => ({ open, setOpen }), [open]);
  return (
    <MobileNavContext.Provider value={value}>{children}</MobileNavContext.Provider>
  );
}

export function useMobileNav(): MobileNavContextValue {
  const ctx = useContext(MobileNavContext);
  if (!ctx) {
    return { open: false, setOpen: () => undefined };
  }
  return ctx;
}
