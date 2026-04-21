import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { router } from "./router/routes";

export default function App(): JSX.Element {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
