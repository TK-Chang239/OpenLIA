import type { JSX } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import "../../components/panic_thermometer/_shared/styles.css";
import { SettingsDrawer } from "../../components/panic_thermometer/SettingsDrawer";
import { DiplomacySection } from "../../components/panic_thermometer/sections/DiplomacySection";
import { FedSection } from "../../components/panic_thermometer/sections/FedSection";
import { Hero } from "../../components/panic_thermometer/sections/Hero";
import { InflationSection } from "../../components/panic_thermometer/sections/InflationSection";
import { OilSection } from "../../components/panic_thermometer/sections/OilSection";
import { ScorecardGrid } from "../../components/panic_thermometer/sections/ScorecardGrid";
import { VerdictBlock } from "../../components/panic_thermometer/sections/VerdictBlock";
import { WageSection } from "../../components/panic_thermometer/sections/WageSection";
import { SEVERITY_LABEL } from "../../components/panic_thermometer/_shared/visuals";
import type { DashboardPayload } from "../../api/panic-thermometer";
import type { Severity } from "../../lib/panic_thermometer/copy/types";
import {
  adaptDiplomacy,
  adaptFed,
  adaptHero,
  adaptInflation,
  adaptOil,
  adaptScorecards,
  adaptSummaryStats,
  adaptVerdict,
  adaptWage,
} from "../../lib/panic_thermometer/adapt";
import { fetchDashboard, importConfig } from "../../api/panic-thermometer";
import { readShareLinkFromUrl } from "../../lib/panic-thermometer/share-link";

const SEVERITY_PILL: Record<Severity, string> = {
  calm: "is-calm",
  elevated: "is-elevated",
  high: "is-high",
  severe: "is-severe",
  crisis: "is-crisis",
};

/** True when every panel is warning about missing data (e.g. no EODHD key). */
function allPanelsUnavailable(p: DashboardPayload): boolean {
  const panels = Object.values(p.panels);
  if (panels.length === 0) return true;
  return panels.every((panel) => panel.status === "disabled" || panel.warnings.length > 0);
}

export default function PanicThermometer(): JSX.Element {
  const { t } = useTranslation();
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [refreshSeconds, setRefreshSeconds] = useState<number | null>(300);
  const [mode, setMode] = useState<"count" | "weighted">("count");

  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setError(null);
    try {
      const payload = await fetchDashboard();
      setDashboard(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // Import a shared config from the URL (?cfg=…) on first mount.
  useEffect(() => {
    const shared = readShareLinkFromUrl();
    if (shared && typeof shared === "object") {
      void importConfig(shared);
    }
  }, []);

  // Initial load.
  useEffect(() => {
    void refetch();
  }, [refetch]);

  // Poll while a refresh interval is set.
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;
  useEffect(() => {
    if (!refreshSeconds || refreshSeconds <= 0) return;
    const id = window.setInterval(() => {
      void refetchRef.current();
    }, refreshSeconds * 1000);
    return () => window.clearInterval(id);
  }, [refreshSeconds]);

  const openDrawer = () => setDrawerOpen(true);
  const closeDrawer = () => setDrawerOpen(false);

  const composite = dashboard?.composite;
  const level = (composite?.level ?? "calm") as Severity;

  return (
    <div className="pt-page">
      <header className="pt-topbar" role="banner">
        <span className="pt-page-title">{t("panic_thermometer.title")}</span>
        <span className="pt-crumb">
          {t("panic_thermometer.crisis_indicators")} ·{" "}
          <strong>{dashboard ? adaptSummaryStats(dashboard).asOfDateLabel : "—"}</strong>
        </span>
        <div className="pt-spacer" />
        {composite ? (
          <span className={`pt-live-pill ${SEVERITY_PILL[level]}`}>
            {SEVERITY_LABEL[level]} ·{" "}
            {t("panic_thermometer.red_of_total", {
              red: composite.red_count,
              total: 5,
            })}
          </span>
        ) : null}
        <button
          type="button"
          className="pt-top-btn"
          onClick={openDrawer}
          aria-label={t("panic_thermometer.open_settings")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
            <circle cx={12} cy={12} r={3} />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4" />
          </svg>
          {t("panic_thermometer.settings")}
        </button>
      </header>

      <div className="pt-scroll">
        <div className="pt-wrap">
          {renderBody()}
        </div>
      </div>

      <SettingsDrawer
        open={drawerOpen}
        onClose={closeDrawer}
        refreshIntervalSeconds={refreshSeconds}
        onRefreshIntervalChange={setRefreshSeconds}
      />
    </div>
  );

  function renderBody(): JSX.Element {
    if (loading && !dashboard) {
      return (
        <div className="pt-state" role="status" aria-live="polite">
          <div className="pt-skeleton-bar" />
          <span>{t("panic_thermometer.loading")}</span>
        </div>
      );
    }

    if (error && !dashboard) {
      return (
        <div className="pt-state is-error" role="alert">
          <strong>{t("panic_thermometer.error_title")}</strong>
          <span>{error}</span>
          <button type="button" className="pt-top-btn" onClick={() => void refetch()}>
            {t("panic_thermometer.retry")}
          </button>
        </div>
      );
    }

    if (!dashboard) {
      return <div className="pt-state" role="status" />;
    }

    if (allPanelsUnavailable(dashboard)) {
      return (
        <div className="pt-state" role="status">
          <strong>{t("panic_thermometer.empty_title")}</strong>
          <span>{t("panic_thermometer.empty_body")}</span>
        </div>
      );
    }

    const d = dashboard;
    return (
      <>
        <div className="pt-anim-up">
          <Hero
            hero={adaptHero(d)}
            stats={adaptSummaryStats(d)}
            mode={mode}
            onModeChange={setMode}
          />
        </div>
        <div className="pt-anim-up pt-anim-d1">
          <ScorecardGrid entries={adaptScorecards(d)} />
        </div>
        <div className="pt-anim-up pt-anim-d2">
          <OilSection panel={adaptOil(d.panels.oil)} onEditRules={openDrawer} />
        </div>
        <div className="pt-anim-up pt-anim-d3">
          <InflationSection panel={adaptInflation(d.panels.inflation)} onEditRules={openDrawer} />
        </div>
        <div className="pt-anim-up pt-anim-d4">
          <FedSection
            panel={adaptFed(d.panels.fed_language)}
            onEditRules={openDrawer}
            onEditKeywords={openDrawer}
          />
        </div>
        <div className="pt-anim-up pt-anim-d5">
          <WageSection panel={adaptWage(d.panels.wage_growth)} onEditRules={openDrawer} />
        </div>
        <div className="pt-anim-up pt-anim-d6">
          <DiplomacySection
            panel={adaptDiplomacy(d.panels.diplomacy)}
            onEditRules={openDrawer}
            onMarkMilestone={openDrawer}
            onOverrideStatus={openDrawer}
          />
        </div>
        <div className="pt-anim-up pt-anim-d8">
          <VerdictBlock verdict={adaptVerdict(d)} variant="severe" />
        </div>
      </>
    );
  }
}
