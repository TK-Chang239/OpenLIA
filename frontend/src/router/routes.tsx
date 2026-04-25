import { createBrowserRouter, Navigate, type RouteObject } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import { MustChangePasswordGate } from "./MustChangePasswordGate";
import { SetupGate } from "./SetupGate";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
import Home from "../pages/Home";
import Repository from "../pages/Repository";
import PortfolioPage from "../pages/PortfolioPage";
import { SettingsPage } from "../pages/SettingsPage";
import { SetupPage } from "../pages/SetupPage";
import { useAuth } from "../auth/AuthContext";
import { SecretaryPage } from "../pages/SecretaryPage";
import EquityResearch from "../pages/departments/EquityResearch";
import EarningsUpdate from "../pages/departments/EarningsUpdate";
import MorningBriefing from "../pages/departments/MorningBriefing";
import RetailSentiment from "../pages/departments/RetailSentiment";
import MacroResearch from "../pages/departments/MacroResearch";
import PanicThermometer from "../pages/departments/PanicThermometer";
import ReportPrintPage from "../pages/ReportPrintPage";

function SecretaryRoute() {
  const { user } = useAuth();
  return (
    <SecretaryPage
      user={{ id: user?.id ?? 'local', display_name: user?.display_name ?? 'there' }}
    />
  );
}

export const routes: RouteObject[] = [
  {
    element: <SetupGate />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
      { path: "/setup", element: <SetupPage /> },
      // Full-bleed print/PDF page. No AppShell so backgrounds/margins are
      // controlled by the print stylesheet, and so the body of the page
      // can be paginated by Playwright/browser print engines cleanly.
      { path: "/reports/:id/render", element: <ReportPrintPage /> },
      {
        element: (
          <ProtectedRoute>
            <MustChangePasswordGate />
          </ProtectedRoute>
        ),
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: "/", element: <Navigate to="/secretary" replace /> },
              { path: "/home", element: <Home /> },
              { path: "/repository", element: <Repository /> },
              { path: "/portfolio", element: <PortfolioPage /> },
              { path: "/settings/*", element: <SettingsPage /> },
              { path: "/secretary", element: <SecretaryRoute /> },
              { path: "/equity-research", element: <EquityResearch /> },
              { path: "/earnings-update", element: <EarningsUpdate /> },
              { path: "/morning-briefing", element: <MorningBriefing /> },
              { path: "/retail-sentiment", element: <RetailSentiment /> },
              { path: "/macro-research/*", element: <MacroResearch /> },
              { path: "/panic-thermometer", element: <PanicThermometer /> },
            ],
          },
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
