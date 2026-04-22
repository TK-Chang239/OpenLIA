import { RouterProvider } from "react-router-dom";
import type { createBrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { router as defaultRouter } from "./router/routes";

type AppRouter = ReturnType<typeof createBrowserRouter>;

interface AppProps {
  router?: AppRouter;
}

export default function App({ router = defaultRouter }: AppProps = {}): JSX.Element {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
