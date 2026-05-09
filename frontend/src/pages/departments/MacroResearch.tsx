import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import {
  getDashboard,
  listDashboards,
  type DashboardSummary,
} from "../../api/macro_research";
import "../../components/macro_research/_shared/styles.css";
import SummaryView from "./macro_research/SummaryView";
import DebtCycleView from "./macro_research/DebtCycleView";
import FourSeasonsView from "./macro_research/FourSeasonsView";
import AllWeatherView from "./macro_research/AllWeatherView";
import WorldOrderView from "./macro_research/WorldOrderView";
import FiveForcesView from "./macro_research/FiveForcesView";
import MRSettingsPanel from "./macro_research/MRSettingsPanel";

interface DashboardTab extends DashboardSummary {
  tcode: string;
}

const FALLBACK_TABS: DashboardTab[] = [
  { slug: "debt_cycle", display_name: "Debt Cycle", tcode: "T1" },
  { slug: "four_seasons", display_name: "Four Seasons", tcode: "T2" },
  { slug: "all_weather", display_name: "All-Weather", tcode: "T3" },
  { slug: "world_order", display_name: "World Order", tcode: "T4" },
  { slug: "five_forces", display_name: "Five Forces", tcode: "T5" },
];

const TCODE_BY_SLUG: Record<string, string> = {
  debt_cycle: "T1",
  four_seasons: "T2",
  all_weather: "T3",
  world_order: "T4",
  five_forces: "T5",
};

const REFRESH_OPTIONS: { label: string; ms: number | null }[] = [
  { label: "Auto-refresh · 5 min", ms: 300_000 },
  { label: "Auto-refresh · 15 min", ms: 900_000 },
  { label: "Auto-refresh · Off", ms: null },
];

const PAGE_EASE = [0.16, 1, 0.3, 1] as const;

export default function MacroResearch(): JSX.Element {
  const [dashboards, setDashboards] = useState<DashboardTab[]>(FALLBACK_TABS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshMs, setRefreshMs] = useState<number | null>(300_000);
  const location = useLocation();
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    listDashboards()
      .then((r) => {
        if (r.dashboards.length === 0) return;
        setDashboards(
          r.dashboards.map((d) => ({ ...d, tcode: TCODE_BY_SLUG[d.slug] ?? "★" })),
        );
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (refreshMs === null) return;
    const segments = location.pathname.split("/").filter(Boolean);
    const activeSlug = segments[segments.length - 1];
    const knownSlugs = new Set(dashboards.map((d) => d.slug));
    if (!activeSlug || !knownSlugs.has(activeSlug)) return;
    const id = window.setInterval(() => {
      getDashboard(activeSlug).catch(() => undefined);
    }, refreshMs);
    return () => window.clearInterval(id);
  }, [refreshMs, location.pathname, dashboards]);

  /* Page-mount entrance: animates the whole macro-research shell in
     when the user navigates from another route. With reduced-motion,
     skip the y-translate but keep a quick fade so the surface still
     feels responsive. */
  const pageMotion = prefersReducedMotion
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.12 } }
    : {
        initial: { opacity: 0, y: 12 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.32, ease: PAGE_EASE },
      };

  /* Per-tab transition: cross-fade with a small y-translate so the
     content feels like it slides into place. mode="wait" ensures the
     outgoing panel finishes exiting before the new one mounts, which
     keeps charts from overlapping during their own paint. */
  const tabMotion = prefersReducedMotion
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.1 } }
    : {
        initial: { opacity: 0, y: 8 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -6 },
        transition: { duration: 0.22, ease: PAGE_EASE },
      };

  return (
    <motion.div
      className="flex h-full flex-col bg-[--color-bg-base]"
      initial={pageMotion.initial}
      animate={pageMotion.animate}
      transition={pageMotion.transition}
    >
      <header className="flex h-[52px] flex-shrink-0 items-center gap-3 border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6">
        <span className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          Macro Research
        </span>
        <span className="ml-3 border-l border-[--color-border-subtle] pl-3 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
          Dalio Frameworks ·{" "}
          <strong className="font-medium text-[--color-feedback-success]">
            Live · TUE 02 MAY 2026
          </strong>
        </span>
        <div className="flex-1" />
        <span className="mr-live-pill" data-testid="mr-live-pill">
          Streaming · 42 series
        </span>
        <select
          aria-label="Auto-refresh interval"
          data-testid="mr-refresh-select"
          value={refreshMs ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            setRefreshMs(v === "" ? null : Number(v));
          }}
          className="h-[30px] rounded-md border border-[--color-border-subtle] bg-transparent pl-2.5 pr-7 font-mono text-[12px] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
        >
          {REFRESH_OPTIONS.map((o) => (
            <option key={o.label} value={o.ms ?? ""}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          data-testid="mr-settings-button"
          onClick={() => setSettingsOpen(true)}
          className="inline-flex h-[30px] items-center gap-1.5 rounded-md border border-[--color-border-subtle] bg-transparent px-3 font-mono text-[12px] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
        >
          <SettingsIcon />
          Settings
        </button>
      </header>

      <nav
        className="flex flex-shrink-0 items-center gap-px overflow-x-auto border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6"
        aria-label="Macro frameworks"
      >
        <SummaryTab path="." prefersReducedMotion={prefersReducedMotion ?? false} />
        {dashboards.map((d) => (
          <TabLink
            key={d.slug}
            to={d.slug}
            tcode={d.tcode}
            label={d.display_name}
            prefersReducedMotion={prefersReducedMotion ?? false}
          />
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto px-8 py-7 pb-16">
        <div className="mx-auto max-w-[1200px]">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={tabMotion.initial}
              animate={tabMotion.animate}
              exit={tabMotion.exit}
              transition={tabMotion.transition}
            >
              <Routes location={location}>
                <Route index element={<SummaryView />} />
                <Route path="debt_cycle" element={<DebtCycleView />} />
                <Route path="four_seasons" element={<FourSeasonsView />} />
                <Route path="all_weather" element={<AllWeatherView />} />
                <Route path="world_order" element={<WorldOrderView />} />
                <Route path="five_forces" element={<FiveForcesView />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {settingsOpen ? (
        <MRSettingsPanel
          dashboards={dashboards}
          onClose={() => setSettingsOpen(false)}
        />
      ) : null}
    </motion.div>
  );
}

function TabLink({
  to,
  tcode,
  label,
  prefersReducedMotion,
}: {
  to: string;
  tcode: string;
  label: string;
  prefersReducedMotion: boolean;
}): JSX.Element {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        "-mb-px relative inline-flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3.5 py-3 text-[13px] " +
        (isActive
          ? "font-medium text-[--color-text-primary]"
          : "text-[--color-text-secondary] hover:text-[--color-text-primary]")
      }
    >
      {({ isActive }) => (
        <>
          <span className={`mr-tab-tcode${isActive ? " is-active" : ""}`}>{tcode}</span>
          {label}
          {isActive ? (
            <motion.span
              layoutId="mr-tab-underline"
              className="absolute -bottom-[2px] left-0 right-0 h-[2px] bg-[--color-text-primary]"
              transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 520, damping: 38 }}
            />
          ) : null}
        </>
      )}
    </NavLink>
  );
}

function SummaryTab({ path, prefersReducedMotion }: { path: string; prefersReducedMotion: boolean }): JSX.Element {
  return (
    <NavLink
      to={path}
      end
      className={({ isActive }) =>
        "-mb-px relative inline-flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3.5 py-3 text-[13px] " +
        (isActive
          ? "font-medium text-[--color-text-primary]"
          : "text-[--color-text-secondary] hover:text-[--color-text-primary]")
      }
    >
      {({ isActive }) => (
        <>
          <span className={`mr-tab-tcode is-summary${isActive ? " is-active" : ""}`}>★</span>
          Summary
          {isActive ? (
            <motion.span
              layoutId="mr-tab-underline"
              className="absolute -bottom-[2px] left-0 right-0 h-[2px] bg-[--color-text-primary]"
              transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 520, damping: 38 }}
            />
          ) : null}
        </>
      )}
    </NavLink>
  );
}

function SettingsIcon(): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3.5 w-3.5"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4" />
    </svg>
  );
}
