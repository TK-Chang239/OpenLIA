import { createBrowserRouter, Navigate, type RouteObject } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import { MustChangePasswordGate } from "./MustChangePasswordGate";
import { SetupGate } from "./SetupGate";
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
import { DeptDisabledBanner } from "../components/sidebar/DeptDisabledBanner";
import { DisclaimerGate } from "./DisclaimerGate";

function WithDeptBanner({
  departmentId,
  children,
}: {
  departmentId: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full flex-col">
      <DeptDisabledBanner departmentId={departmentId} />
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

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
      // Login pages disabled — redirect any attempt back to the shell.
      { path: "/login", element: <Navigate to="/" replace /> },
      { path: "/register", element: <Navigate to="/" replace /> },
      { path: "/forgot-password", element: <Navigate to="/" replace /> },
      { path: "/reset-password", element: <Navigate to="/" replace /> },
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
            element: <DisclaimerGate />,
            children: [
              {
                element: <AppLayout />,
                children: [
                  { path: "/", element: <Home /> },
                  { path: "/home", element: <Navigate to="/" replace /> },
                  { path: "/repository", element: <Repository /> },
                  { path: "/portfolio", element: <PortfolioPage /> },
                  { path: "/settings/*", element: <SettingsPage /> },
                  {
                    path: "/secretary",
                    element: (
                      <WithDeptBanner departmentId="secretary">
                        <SecretaryRoute />
                      </WithDeptBanner>
                    ),
                  },
                  {
                    path: "/equity-research",
                    element: (
                      <WithDeptBanner departmentId="equity_research">
                        <EquityResearch />
                      </WithDeptBanner>
                    ),
                  },
                  {
                    path: "/earnings-update",
                    element: (
                      <WithDeptBanner departmentId="earnings_update">
                        <EarningsUpdate />
                      </WithDeptBanner>
                    ),
                  },
                  {
                    path: "/morning-briefing",
                    element: (
                      <WithDeptBanner departmentId="morning_briefing">
                        <MorningBriefing />
                      </WithDeptBanner>
                    ),
                  },
                  {
                    path: "/retail-sentiment",
                    element: (
                      <WithDeptBanner departmentId="retail_sentiment">
                        <RetailSentiment />
                      </WithDeptBanner>
                    ),
                  },
                  {
                    path: "/macro-research/*",
                    element: (
                      <WithDeptBanner departmentId="macro_research">
                        <MacroResearch />
                      </WithDeptBanner>
                    ),
                  },
                  {
                    path: "/panic-thermometer",
                    element: (
                      <WithDeptBanner departmentId="panic_thermometer">
                        <PanicThermometer />
                      </WithDeptBanner>
                    ),
                  },
                ],
              },
            ],
          },
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
