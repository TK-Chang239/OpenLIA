import type { JSX } from "react";
import { RouterProvider } from "react-router-dom";
import type { createBrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { useTimezoneAutoCapture } from "./auth/useTimezoneAutoCapture";
import { useBeforeUnloadBeacon } from "./app/useBeforeUnloadBeacon";
import { useUiLanguageSync } from "./i18n/useUiLanguage";
import { router as defaultRouter } from "./router/routes";
import { ErrorBoundary } from "./components/shell/ErrorBoundary";

type AppRouter = ReturnType<typeof createBrowserRouter>;

interface AppProps {
  router?: AppRouter;
}

function AuthedShell({ router }: { router: AppRouter }): JSX.Element {
  useTimezoneAutoCapture();
  useBeforeUnloadBeacon();
  useUiLanguageSync();
  return <RouterProvider router={router} />;
}

export default function App({ router = defaultRouter }: AppProps = {}): JSX.Element {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AuthedShell router={router} />
      </AuthProvider>
    </ErrorBoundary>
  );
}
