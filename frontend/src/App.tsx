import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { RouterProvider } from "react-router-dom";
import type { createBrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { router as defaultRouter } from "./router/routes";
import { getStatus } from "./api/setup";

function SetupGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "needs_setup" | "done">("loading");

  useEffect(() => {
    void (async () => {
      try {
        const status = await getStatus();
        setState(status.wizard_completed ? "done" : "needs_setup");
      } catch {
        setState("done"); // backend unreachable; let AuthProvider handle it
      }
    })();
  }, []);

  if (state === "loading") return null;
  if (state === "needs_setup" && window.location.pathname !== "/setup") {
    window.location.replace("/setup");
    return null;
  }
  return <>{children}</>;
}

type AppRouter = ReturnType<typeof createBrowserRouter>;

interface AppProps {
  router?: AppRouter;
}

export default function App({ router = defaultRouter }: AppProps = {}): JSX.Element {
  return (
    <SetupGate>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </SetupGate>
  );
}
