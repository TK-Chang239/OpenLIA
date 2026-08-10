import { useCallback, useState } from "react";
import { MockupEmbed } from "../embed/MockupEmbed";
import { OverlayEmbed } from "../embed/OverlayEmbed";
import {
  V3ReportSettingsModal,
  type V3SettingsValue,
} from "../../components/equity-research-v3/V3ReportSettingsModal";

// Equity Research — the adopted mockup (conversational report generator). The
// mockup's own Report Settings modal is stripped and replaced with the app's V3
// modal (opened from the mode crumb), and "Open Report" opens the AAPL report.
const STRIP = ["#settingsModal", ".modal-backdrop"];

const DEMO_SETTINGS: V3SettingsValue = {
  length: "normal",
  language: "en",
  reasoningEffort: "medium",
  templateId: "initiation_default",
  templateName: "Stock Initiation",
  instructionsId: null,
  instructionsName: null,
};

export default function DemoEquityResearch(): JSX.Element {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  const wire = useCallback((root: ShadowRoot) => {
    const openSettings = () => setSettingsOpen(true);
    const openReport = () => setReportOpen(true);

    const triggers = Array.from(
      root.querySelectorAll<HTMLElement>(".crumb-mode, .mode-pill"),
    );
    triggers.forEach((el) => {
      el.style.cursor = "pointer";
      el.addEventListener("click", openSettings);
    });

    const openBtn = Array.from(
      root.querySelectorAll<HTMLElement>(".rc-actions button, .rc-actions a"),
    ).find((el) => /open report/i.test(el.textContent ?? ""));
    openBtn?.addEventListener("click", openReport);

    return () => {
      triggers.forEach((el) => el.removeEventListener("click", openSettings));
      openBtn?.removeEventListener("click", openReport);
    };
  }, []);

  return (
    <>
      <MockupEmbed url="/demo-mockups/equity-research.html" strip={STRIP} onReady={wire} />

      <V3ReportSettingsModal
        open={settingsOpen}
        value={DEMO_SETTINGS}
        onClose={() => setSettingsOpen(false)}
        onSave={() => setSettingsOpen(false)}
        onUploadClick={() => undefined}
        onUploadInstructionsClick={() => undefined}
      />

      {reportOpen && (
        <OverlayEmbed
          url="/demo-mockups/report-aapl.html"
          label="AAPL Initiation Report"
          onClose={() => setReportOpen(false)}
        />
      )}
    </>
  );
}
