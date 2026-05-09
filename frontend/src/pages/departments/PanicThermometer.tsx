import type { JSX } from "react";
import { useEffect, useState } from "react";
import "../../components/panic_thermometer/_shared/styles.css";
import { SettingsDrawer } from "../../components/panic_thermometer/SettingsDrawer";
import { DiplomacySection } from "../../components/panic_thermometer/sections/DiplomacySection";
import { FedSection } from "../../components/panic_thermometer/sections/FedSection";
import { Hero } from "../../components/panic_thermometer/sections/Hero";
import { InflationSection } from "../../components/panic_thermometer/sections/InflationSection";
import { OilSection } from "../../components/panic_thermometer/sections/OilSection";
import { ReleasesTable } from "../../components/panic_thermometer/sections/ReleasesTable";
import { ScorecardGrid } from "../../components/panic_thermometer/sections/ScorecardGrid";
import { VerdictBlock } from "../../components/panic_thermometer/sections/VerdictBlock";
import { WageSection } from "../../components/panic_thermometer/sections/WageSection";
import { SEVERITY_LABEL } from "../../components/panic_thermometer/_shared/visuals";
import {
  diplomacyPanel,
  fedPanel,
  inflationPanel,
  oilPanel,
  wagePanel,
} from "../../lib/panic_thermometer/copy/panels";
import { releaseRows } from "../../lib/panic_thermometer/copy/releases";
import { heroCopy, scorecards, summaryStats } from "../../lib/panic_thermometer/copy/summary";
import { verdictCopy } from "../../lib/panic_thermometer/copy/verdict";
import { importConfig } from "../../api/panic-thermometer";
import { readShareLinkFromUrl } from "../../lib/panic-thermometer/share-link";

export default function PanicThermometer(): JSX.Element {
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [refreshSeconds, setRefreshSeconds] = useState<number | null>(300);
  const [mode, setMode] = useState<"count" | "weighted">("count");

  useEffect(() => {
    const shared = readShareLinkFromUrl();
    if (shared && typeof shared === "object") {
      void importConfig(shared);
    }
  }, []);

  const openDrawer = () => setDrawerOpen(true);
  const closeDrawer = () => setDrawerOpen(false);

  const livePillClass = (() => {
    switch (summaryStats.composite) {
      case "calm":
        return "is-calm";
      case "elevated":
        return "is-elevated";
      case "high":
        return "is-high";
      case "severe":
        return "is-severe";
      case "crisis":
        return "is-crisis";
    }
  })();

  return (
    <div className="pt-page">
      <header className="pt-topbar" role="banner">
        <span className="pt-page-title">Panic Thermometer</span>
        <span className="pt-crumb">
          Crisis indicators · <strong>{summaryStats.asOfDateLabel}</strong>
        </span>
        <div className="pt-spacer" />
        <span className={`pt-live-pill ${livePillClass}`}>
          {SEVERITY_LABEL[summaryStats.composite]} · {summaryStats.redCount} of{" "}
          {summaryStats.totalPanels} red
        </span>
        <button
          type="button"
          className="pt-top-btn"
          onClick={openDrawer}
          aria-label="Open settings"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
            <circle cx={12} cy={12} r={3} />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4" />
          </svg>
          Settings
        </button>
      </header>

      <div className="pt-scroll">
        <div className="pt-wrap">
          <div className="pt-anim-up">
            <Hero
              hero={heroCopy}
              stats={summaryStats}
              mode={mode}
              onModeChange={setMode}
            />
          </div>
          <div className="pt-anim-up pt-anim-d1">
            <ScorecardGrid entries={scorecards} />
          </div>
          <div className="pt-anim-up pt-anim-d2">
            <OilSection panel={oilPanel} onEditRules={openDrawer} />
          </div>
          <div className="pt-anim-up pt-anim-d3">
            <InflationSection panel={inflationPanel} onEditRules={openDrawer} />
          </div>
          <div className="pt-anim-up pt-anim-d4">
            <FedSection
              panel={fedPanel}
              onEditRules={openDrawer}
              onEditKeywords={openDrawer}
            />
          </div>
          <div className="pt-anim-up pt-anim-d5">
            <WageSection panel={wagePanel} onEditRules={openDrawer} />
          </div>
          <div className="pt-anim-up pt-anim-d6">
            <DiplomacySection
              panel={diplomacyPanel}
              onEditRules={openDrawer}
              onMarkMilestone={openDrawer}
              onOverrideStatus={openDrawer}
            />
          </div>
          <div className="pt-anim-up pt-anim-d7">
            <ReleasesTable rows={releaseRows} />
          </div>
          <div className="pt-anim-up pt-anim-d8">
            <VerdictBlock verdict={verdictCopy} variant="severe" />
          </div>
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
}
