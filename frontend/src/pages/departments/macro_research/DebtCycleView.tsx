import { useCallback, useEffect, useState } from "react";
import {
  getDashboard,
  runAssessment,
  type DashboardResult,
} from "../../../api/macro_research";
import {
  AssessmentBlock,
  ErrorBlock,
  FreshnessBadge,
  LoadingBlock,
  Panel,
  SeverityPill,
  SmartModeToggle,
  tierOf,
} from "./DashboardFrame";

const STATUS_DOT: Record<string, string> = {
  green: "bg-[--color-feedback-success]",
  amber: "bg-[--color-feedback-warning]",
  red: "bg-[--color-feedback-error]",
};

export default function DebtCycleView(): JSX.Element {
  const [data, setData] = useState<DashboardResult | null>(null);
  const [smartMode, setSmartMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const load = useCallback((sm: boolean) => {
    getDashboard("debt_cycle", sm)
      .then((r) => {
        setData(r);
        setError(null);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  useEffect(() => {
    load(smartMode);
  }, [load, smartMode]);

  const onRun = async () => {
    setRunning(true);
    try {
      await runAssessment("debt_cycle");
      load(smartMode);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  if (error) return <ErrorBlock message={error} />;
  if (!data) return <LoadingBlock label="Debt Cycle" />;

  const t3 = tierOf(data, "T3")?.data as
    | {
        phase?: string;
        indicator_statuses?: Record<string, string>;
        monetary_space?: {
          rate_cut_headroom?: number;
          qe_credibility?: string;
          currency_debasement_risk?: string;
        };
        watchlist_triggers?: { name: string; status: string }[];
      }
    | undefined;
  const t4 = tierOf(data, "T4")?.data as { assessment?: string } | undefined;

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-[--color-text-primary]">
            Debt Cycle
          </h2>
          <SeverityPill severity={data.severity} />
          <FreshnessBadge generatedAt={data.generated_at} />
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
        <Panel title="Phase">
          <div className="text-2xl font-semibold text-[--color-text-primary]">
            {t3?.phase ?? data.headline ?? "Unknown"}
          </div>
        </Panel>
        <Panel title="Monetary Space">
          <ul className="space-y-1 text-sm text-[--color-text-primary]">
            <li>
              Rate-cut headroom:{" "}
              <span className="font-mono">
                {typeof t3?.monetary_space?.rate_cut_headroom === "number"
                  ? t3.monetary_space.rate_cut_headroom.toFixed(2)
                  : "—"}
              </span>
            </li>
            <li>QE credibility: {t3?.monetary_space?.qe_credibility ?? "—"}</li>
            <li>
              Currency debasement risk:{" "}
              {t3?.monetary_space?.currency_debasement_risk ?? "—"}
            </li>
          </ul>
        </Panel>
        <Panel title="Indicators">
          <ul className="space-y-1 text-sm">
            {Object.entries(t3?.indicator_statuses ?? {}).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between">
                <span className="text-[--color-text-primary]">{k}</span>
                <span className="flex items-center gap-2 text-[--color-text-secondary]">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      STATUS_DOT[v] ?? "bg-[--color-border-subtle]"
                    }`}
                  />
                  {v}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Watchlist Triggers">
          <ul className="space-y-1 text-sm">
            {(t3?.watchlist_triggers ?? []).map((w) => (
              <li
                key={w.name}
                className="flex items-center justify-between text-[--color-text-primary]"
              >
                <span>{w.name}</span>
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${
                    STATUS_DOT[w.status] ?? "bg-[--color-border-subtle]"
                  }`}
                />
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <AssessmentBlock
        text={t4?.assessment ?? null}
        generatedAt={data.generated_at}
      />
      {smartMode ? (
        <div className="text-xs text-[--color-text-tertiary]">
          Smart Mode overlays are informational only; backend assessment is
          unchanged.
        </div>
      ) : null}
    </section>
  );
}
