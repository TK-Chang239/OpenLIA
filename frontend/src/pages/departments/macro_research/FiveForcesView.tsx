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
  force_scores?: Record<string, number>;
  active_force_count?: number;
  bucket?: string;
};

const FORCE_LABEL: Record<string, string> = {
  debt_money: "Debt & Money",
  political: "Political",
  geopolitical: "Geopolitical",
  technology: "Technology",
  natural: "Natural",
};

export default function FiveForcesView(): JSX.Element {
  const [data, setData] = useState<DashboardResult | null>(null);
  const [smartMode, setSmartMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    getDashboard("five_forces")
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
      await runAssessment("five_forces");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  if (error) return <ErrorBlock message={error} />;
  if (!data) return <LoadingBlock label="Five Forces" />;

  const t3 = tierOf(data, "T3")?.data as T3 | undefined;
  const t4 = tierOf(data, "T4")?.data as { assessment?: string } | undefined;
  const forces = t3?.force_scores ?? {};

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-[--color-text-primary]">
            Five Forces
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

      <Panel title="Active Force Count" testid="active-force-panel">
        <div className="flex items-center justify-between">
          <div className="text-3xl font-semibold text-[--color-text-primary]">
            {t3?.active_force_count ?? 0}
            <span className="ml-2 text-base font-normal text-[--color-text-secondary]">
              / 5
            </span>
          </div>
          <div className="text-sm text-[--color-text-secondary]">
            {t3?.bucket ?? "—"}
          </div>
        </div>
      </Panel>

      <Panel title="Force Scorecard">
        <ul className="space-y-2 text-sm">
          {Object.keys(FORCE_LABEL).map((key) => {
            const score = forces[key] ?? 0;
            const active = score >= 7;
            return (
              <li
                key={key}
                className="flex items-center gap-3"
                data-testid={`force-row-${key}`}
              >
                <span className="w-36 text-[--color-text-primary]">
                  {FORCE_LABEL[key]}
                </span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-[--color-border-subtle]">
                  <div
                    className={
                      "absolute inset-y-0 left-0 " +
                      (active
                        ? "bg-[--color-feedback-error]"
                        : "bg-[--color-accent-primary]")
                    }
                    style={{ width: `${Math.min(100, (score / 10) * 100)}%` }}
                  />
                </div>
                <span className="w-8 text-right font-mono text-xs text-[--color-text-secondary]">
                  {score}
                </span>
              </li>
            );
          })}
        </ul>
      </Panel>

      <AssessmentBlock
        text={t4?.assessment ?? null}
        generatedAt={data.generated_at}
      />
      {smartMode ? (
        <div className="text-xs text-[--color-text-tertiary]">
          Smart Mode lowers the active threshold during historical turning-point
          windows.
        </div>
      ) : null}
    </section>
  );
}
