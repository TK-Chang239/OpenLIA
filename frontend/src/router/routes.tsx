import { lazy, Suspense } from "react";
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
import { MemoryPage } from "../pages/MemoryPage";
import { useAuth } from "../auth/AuthContext";
import { SecretaryPage } from "../pages/SecretaryPage";
import EquityResearch from "../pages/departments/EquityResearch";
import EquityResearchV3 from "../pages/departments/EquityResearchV3";
import EarningsUpdate from "../pages/departments/EarningsUpdate";
import MorningBriefing from "../pages/departments/MorningBriefing";
import RetailSentiment from "../pages/departments/RetailSentiment";
/* MacroResearch is lazy-loaded — pulls in echarts which is ~400KB gz. */
const MacroResearch = lazy(() => import("../pages/departments/MacroResearch"));
import PanicThermometer from "../pages/departments/PanicThermometer";
import ReportPrintPage from "../pages/ReportPrintPage";
import ReportPrintPageV2 from "../pages/ReportPrintPageV2";
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

function MacroSuspenseFallback() {
  return (
    <div className="flex h-full flex-col bg-[--color-bg-base]">
      <div className="flex h-[52px] flex-shrink-0 items-center gap-3 border-b border-[--color-border-subtle] px-6">
        <span className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          Macro Research
        </span>
        <span className="ml-3 border-l border-[--color-border-subtle] pl-3 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
          Loading dashboards…
        </span>
      </div>
      <div className="flex flex-1 items-center justify-center">
        <div className="h-1 w-32 overflow-hidden rounded-full bg-[--color-bg-code]">
          <div className="mr-suspense-bar h-full w-1/3 rounded-full bg-[--color-accent-primary]" />
        </div>
      </div>
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
      // v2.2 pipeline_run equivalent — backend export pipeline navigates
      // here for PDF/DOCX render, runs the v2→v1 block adapter, then
      // hands the schema to the same ReportRenderer.
      { path: "/reports/v2/:runId/render", element: <ReportPrintPageV2 /> },
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
                  { path: "/portfolio", element: <Navigate to="/portfolio/us" replace /> },
                  { path: "/portfolio/:market", element: <PortfolioPage /> },
                  { path: "/memory", element: <MemoryPage /> },
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
                    // v3 single-model engine. Gated server-side by
                    // REPORT_ENGINE_VERSION=v3; the page surfaces a
                    // clear banner when the engine is disabled.
                    path: "/equity-research-v3",
                    element: (
                      <WithDeptBanner departmentId="equity_research">
                        <EquityResearchV3 />
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
                        <Suspense fallback={<MacroSuspenseFallback />}>
                          <MacroResearch />
                        </Suspense>
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
