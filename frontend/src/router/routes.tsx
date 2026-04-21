import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import Home from "../pages/Home";
import Repository from "../pages/Repository";
import Settings from "../pages/Settings";
import Login from "../pages/Login";
import Setup from "../pages/Setup";
import Secretary from "../pages/departments/Secretary";
import EquityResearch from "../pages/departments/EquityResearch";
import EarningsUpdate from "../pages/departments/EarningsUpdate";
import MorningBriefing from "../pages/departments/MorningBriefing";
import RetailSentiment from "../pages/departments/RetailSentiment";
import MacroResearch from "../pages/departments/MacroResearch";
import PanicThermometer from "../pages/departments/PanicThermometer";

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/setup", element: <Setup /> },
  {
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: "/", element: <Navigate to="/secretary" replace /> },
      { path: "/repository", element: <Repository /> },
      { path: "/settings", element: <Settings /> },
      { path: "/home", element: <Home /> },
      { path: "/secretary", element: <Secretary /> },
      { path: "/equity-research", element: <EquityResearch /> },
      { path: "/earnings-update", element: <EarningsUpdate /> },
      { path: "/morning-briefing", element: <MorningBriefing /> },
      { path: "/retail-sentiment", element: <RetailSentiment /> },
      { path: "/macro-research", element: <MacroResearch /> },
      { path: "/panic-thermometer", element: <PanicThermometer /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
