import { useEffect, useState } from "react";
import type { JSX, ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { getStatus } from "../api/setup";

type SetupStatus = "loading" | "needs_setup" | "done";

interface SetupGateProps {
  children?: ReactNode;
}

export function SetupGate({ children }: SetupGateProps = {}): JSX.Element | null {
  const [state, setState] = useState<SetupStatus>("loading");
  const location = useLocation();

  useEffect(() => {
    void (async () => {
      try {
        const status = await getStatus();
        setState(status.wizard_completed ? "done" : "needs_setup");
      } catch {
        setState("done");
      }
    })();
  }, []);

  if (state === "loading") return null;
  if (state === "needs_setup" && location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }
  return <>{children ?? <Outlet />}</>;
}
