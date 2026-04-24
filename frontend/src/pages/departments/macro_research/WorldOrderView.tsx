import { useCallback, useEffect, useState } from "react";
import {
  getDashboard,
  runAssessment,
  type DashboardResult,
} from "../../../api/macro_research";
import {
  AssessmentBlock,
  ErrorBlock,
  LoadingBlock,
  Panel,
  SeverityPill,
  SmartModeToggle,
  tierOf,
} from "./DashboardFrame";

type T3 = {
  wealth_shift_stage?: "early" | "mid" | "late";
  wealth_shift_components?: {
    institutional?: number;
    market?: number;
    geopolitical?: number;
    retail?: number;
  };
};

const STAGE_LABEL: Record<string, string> = {
  early: "Early — Reserve Intact",
  mid: "Mid — Erosion Underway",
  late: "Late — Succession Phase",
};

export default function WorldOrderView(): JSX.Element {
  const [data, setData] = useState<DashboardResult | null>(null);
  const [smartMode, setSmartMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    getDashboard("world_order")
      .then((r) => {
        setData(r);
        setError(null);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRun = async () => {
    setRunning(true);
    try {
      await runAssessment("world_order");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  if (error) return <ErrorBlock message={error} />;
  if (!data) return <LoadingBlock label="World Order" />;

  const t3 = tierOf(data, "T3")?.data as T3 | undefined;
  const t4 = tierOf(data, "T4")?.data as { assessment?: string } | undefined;
  const components = t3?.wealth_shift_components ?? {};

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-[--color-text-primary]">
            World Order
          </h2>
          <SeverityPill severity={data.severity} />
        </div>
        <div className="flex items-center gap-3">
          <SmartModeToggle value={smartMode} onChange={setSmartMode} />
          <button
            type="button"
            disabled={running}
            onClick={onRun}
            className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1.5 text-sm text-[--color-text-primary] disabled:opacity-60"
          >
            {running ? "Running…" : "Run assessment now"}
          </button>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Empire Stage">
          <div className="text-2xl font-semibold text-[--color-text-primary]">
            {STAGE_LABEL[t3?.wealth_shift_stage ?? ""] ??
              (t3?.wealth_shift_stage ?? "Unknown")}
          </div>
        </Panel>
        <Panel title="Reserve Currency Health">
          <div className="text-sm text-[--color-text-secondary]">
            Aggregated from institutional, market, geopolitical, and retail
            shift components. See Wealth Shift panel for per-axis tiers.
          </div>
        </Panel>
        <Panel title="Wealth Shift Components" testid="wealth-shift-panel">
          <ul className="space-y-1 text-sm text-[--color-text-primary]">
            <li className="flex justify-between">
              <span>Institutional</span>
              <span className="font-mono">{components.institutional ?? "—"}</span>
            </li>
            <li className="flex justify-between">
              <span>Market</span>
              <span className="font-mono">{components.market ?? "—"}</span>
            </li>
            <li className="flex justify-between">
              <span>Geopolitical</span>
              <span className="font-mono">{components.geopolitical ?? "—"}</span>
            </li>
            <li className="flex justify-between">
              <span>Retail</span>
              <span className="font-mono">{components.retail ?? "—"}</span>
            </li>
          </ul>
          <div className="mt-2 text-xs text-[--color-text-tertiary]">
            1 = early, 2 = mid, 3 = late stage per axis.
          </div>
        </Panel>
        <Panel title="Headline">
          <div className="text-sm text-[--color-text-primary]">
            {data.headline ?? "—"}
          </div>
        </Panel>
      </div>

      <AssessmentBlock
        text={t4?.assessment ?? null}
        generatedAt={data.generated_at}
      />
      {smartMode ? (
        <div className="text-xs text-[--color-text-tertiary]">
          Smart Mode weights wealth-shift axes by recent news-cycle volatility.
        </div>
      ) : null}
    </section>
  );
}
