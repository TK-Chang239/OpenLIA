import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import {
  getDashboard,
  listDashboards,
  type DashboardSummary,
} from "../../api/macro_research";
import SummaryView from "./macro_research/SummaryView";
import DebtCycleView from "./macro_research/DebtCycleView";
import FourSeasonsView from "./macro_research/FourSeasonsView";
import AllWeatherView from "./macro_research/AllWeatherView";
import WorldOrderView from "./macro_research/WorldOrderView";
import FiveForcesView from "./macro_research/FiveForcesView";
import MRSettingsPanel from "./macro_research/MRSettingsPanel";

const FALLBACK_TABS: DashboardSummary[] = [
  { slug: "debt_cycle", display_name: "Debt Cycle" },
  { slug: "four_seasons", display_name: "Four Seasons" },
  { slug: "all_weather", display_name: "All-Weather" },
  { slug: "world_order", display_name: "World Order" },
  { slug: "five_forces", display_name: "Five Forces" },
];

const REFRESH_OPTIONS: { label: string; ms: number | null }[] = [
  { label: "Off", ms: null },
  { label: "1m", ms: 60_000 },
  { label: "5m", ms: 300_000 },
  { label: "15m", ms: 900_000 },
];

export default function MacroResearch(): JSX.Element {
  const [dashboards, setDashboards] = useState<DashboardSummary[]>(FALLBACK_TABS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshMs, setRefreshMs] = useState<number | null>(null);
  const location = useLocation();

  useEffect(() => {
    listDashboards()
      .then((r) => {
        if (r.dashboards.length > 0) {
          setDashboards(r.dashboards);
        }
      })
      .catch(() => {
        /* keep fallback tabs */
      });
  }, []);

  // Auto-refresh polling for the active dashboard tab.
  useEffect(() => {
    if (refreshMs === null) return;
    const segments = location.pathname.split("/").filter(Boolean);
    const activeSlug = segments[segments.length - 1];
    const knownSlugs = new Set(dashboards.map((d) => d.slug));
    if (!activeSlug || !knownSlugs.has(activeSlug)) return;
    const id = window.setInterval(() => {
      // Fire-and-forget: views own their own data state but a refresh
      // here keeps any cached fetches warm and surfaces the latest
      // assessment freshness on the active tab.
      getDashboard(activeSlug).catch(() => {
        /* ignore polling errors */
      });
    }, refreshMs);
    return () => window.clearInterval(id);
  }, [refreshMs, location.pathname, dashboards]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6">
        <h1 className="text-xl font-semibold text-[--color-text-primary]">
          Macro Research
        </h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-[--color-text-secondary]">
            <span>Auto-refresh</span>
            <select
              aria-label="Auto-refresh interval"
              data-testid="mr-refresh-select"
              value={refreshMs ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setRefreshMs(v === "" ? null : Number(v));
              }}
              className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-1 text-xs text-[--color-text-primary]"
            >
              {REFRESH_OPTIONS.map((o) => (
                <option key={o.label} value={o.ms ?? ""}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            data-testid="mr-settings-button"
            className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1.5 text-sm text-[--color-text-primary] hover:border-[--color-accent-primary]"
            onClick={() => setSettingsOpen(true)}
          >
            Settings
          </button>
        </div>
      </header>
      <nav className="flex items-center gap-1 border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6">
        <NavLink
          to="."
          end
          className={({ isActive }) =>
            "cursor-pointer px-4 py-2.5 text-sm " +
            (isActive
              ? "border-b-2 border-[--color-text-primary] font-medium text-[--color-text-primary]"
              : "text-[--color-text-secondary] hover:text-[--color-text-primary]")
          }
        >
          Summary
        </NavLink>
        {dashboards.map((d) => (
          <NavLink
            key={d.slug}
            to={d.slug}
            className={({ isActive }) =>
              "cursor-pointer px-4 py-2.5 text-sm " +
              (isActive
                ? "border-b-2 border-[--color-text-primary] font-medium text-[--color-text-primary]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]")
            }
          >
            {d.display_name}
          </NavLink>
        ))}
      </nav>
      <div className="flex-1 overflow-auto p-6">
        <Routes>
          <Route index element={<SummaryView dashboards={dashboards} />} />
          <Route path="debt_cycle" element={<DebtCycleView />} />
          <Route path="four_seasons" element={<FourSeasonsView />} />
          <Route path="all_weather" element={<AllWeatherView />} />
          <Route path="world_order" element={<WorldOrderView />} />
          <Route path="five_forces" element={<FiveForcesView />} />
        </Routes>
      </div>
      {settingsOpen ? (
        <MRSettingsPanel
          dashboards={dashboards}
          onClose={() => setSettingsOpen(false)}
        />
      ) : null}
    </div>
  );
}
