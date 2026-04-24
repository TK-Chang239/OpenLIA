import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import {
  listDashboards,
  type DashboardSummary,
} from "../../api/macro_research";
import SummaryView from "./macro_research/SummaryView";
import DebtCycleView from "./macro_research/DebtCycleView";
import FourSeasonsView from "./macro_research/FourSeasonsView";
import AllWeatherView from "./macro_research/AllWeatherView";
import WorldOrderView from "./macro_research/WorldOrderView";
import FiveForcesView from "./macro_research/FiveForcesView";
import ScheduleEditor from "./macro_research/ScheduleEditor";

const FALLBACK_TABS: DashboardSummary[] = [
  { slug: "debt_cycle", display_name: "Debt Cycle" },
  { slug: "four_seasons", display_name: "Four Seasons" },
  { slug: "all_weather", display_name: "All-Weather" },
  { slug: "world_order", display_name: "World Order" },
  { slug: "five_forces", display_name: "Five Forces" },
];

export default function MacroResearch(): JSX.Element {
  const [dashboards, setDashboards] = useState<DashboardSummary[]>(FALLBACK_TABS);
  const [scheduleOpen, setScheduleOpen] = useState(false);

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

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6">
        <h1 className="text-xl font-semibold text-[--color-text-primary]">
          Macro Research
        </h1>
        <button
          type="button"
          className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1.5 text-sm text-[--color-text-primary] hover:border-[--color-accent-primary]"
          onClick={() => setScheduleOpen(true)}
        >
          Schedule
        </button>
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
      {scheduleOpen ? (
        <ScheduleEditor onClose={() => setScheduleOpen(false)} />
      ) : null}
    </div>
  );
}
