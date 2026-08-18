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
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
import { useAuth } from "../auth/AuthContext";
import { SecretaryPage } from "../pages/SecretaryPage";
import EquityResearchV3 from "../pages/departments/EquityResearchV3";
import EarningsUpdate from "../pages/departments/EarningsUpdate";
import MorningBriefing from "../pages/departments/MorningBriefing";
import RetailSentiment from "../pages/departments/RetailSentiment";
/* MacroResearch is lazy-loaded — pulls in echarts which is ~400KB gz. */
const MacroResearch = lazy(() => import("../pages/departments/MacroResearch"));

/* Demo mode swaps four pages for the adopted mockup designs (Shadow-DOM
   embeds). Guarded so none of this ships in the normal build. */
const DEMO = import.meta.env.VITE_DEMO_MODE === "true";
const DemoSecretary = DEMO ? lazy(() => import("../demo/pages/DemoSecretary")) : null;
const DemoEquityResearch = DEMO ? lazy(() => import("../demo/pages/DemoEquityResearch")) : null;
const DemoMorningBriefing = DEMO ? lazy(() => import("../demo/pages/DemoMorningBriefing")) : null;
const DemoRepository = DEMO ? lazy(() => import("../demo/pages/DemoRepository")) : null;

function demoOr(
  Demo: React.LazyExoticComponent<React.ComponentType> | null,
  real: React.ReactNode,
): React.ReactNode {
  if (DEMO && Demo) {
    return (
      <Suspense fallback={null}>
        <Demo />
      </Suspense>
    );
  }
  return real;
}
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
      user={{ id: user?.id ?? 'local', display_name: user?.display_name ?? '' }}
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
            element: <DisclaimerGate />,
            children: [
              {
                element: <AppLayout />,
                children: [
                  { path: "/", element: <Home /> },
                  { path: "/home", element: <Navigate to="/" replace /> },
                  { path: "/repository", element: demoOr(DemoRepository, <Repository />) },
                  { path: "/portfolio", element: <Navigate to="/portfolio/us" replace /> },
                  { path: "/portfolio/:market", element: <PortfolioPage /> },
                  {
                    path: "/memory",
                    element: DEMO ? <Navigate to="/" replace /> : <MemoryPage />,
                  },
                  { path: "/settings/*", element: <SettingsPage /> },
                  {
                    path: "/secretary",
                    element: demoOr(
                      DemoSecretary,
                      <WithDeptBanner departmentId="secretary">
                        <SecretaryRoute />
                      </WithDeptBanner>,
                    ),
                  },
                  {
                    // v3 single-model engine — the sole equity-research engine.
                    path: "/equity-research",
                    element: demoOr(
                      DemoEquityResearch,
                      <WithDeptBanner departmentId="equity_research">
                        <EquityResearchV3 />
                      </WithDeptBanner>,
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
                    element: demoOr(
                      DemoMorningBriefing,
                      <WithDeptBanner departmentId="morning_briefing">
                        <MorningBriefing />
                      </WithDeptBanner>,
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

// Serve correctly when the app is hosted under a sub-path (e.g. GitHub Pages
// project site at /openlia-demo/). BASE_URL is "/" for normal builds — no-op —
// and the Vite --base value for the demo build. React Router wants a leading
// but no trailing slash.
const routerBasename = import.meta.env.BASE_URL.replace(/\/+$/, "") || "/";

export const router = createBrowserRouter(routes, { basename: routerBasename });
