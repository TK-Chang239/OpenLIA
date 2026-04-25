import { useCallback, useEffect, useState } from "react";
import {
  getDashboard,
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

type T3 = {
  portfolio_source?: "user" | "fallback_60_40";
  portfolio?: Record<string, number>;
  reference_allocation?: Record<string, number>;
  risk_contributions?: Record<string, number>;
  reference_risk_contributions?: Record<string, number>;
  season_coverage?: Record<string, string>;
  gold_gap?: number;
  overall_coverage_label?: string;
};

const COVERAGE_CELL: Record<string, string> = {
  green: "bg-[--color-feedback-success] text-white",
  amber: "bg-[--color-feedback-warning] text-black",
  red: "bg-[--color-feedback-error] text-white",
};

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export default function AllWeatherView(): JSX.Element {
  const [data, setData] = useState<DashboardResult | null>(null);
  const [smartMode, setSmartMode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((sm: boolean) => {
    getDashboard("all_weather", sm)
      .then((r) => {
        setData(r);
        setError(null);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  useEffect(() => {
    load(smartMode);
  }, [load, smartMode]);

  if (error) return <ErrorBlock message={error} />;
  if (!data) return <LoadingBlock label="All-Weather" />;

  const t3 = tierOf(data, "T3")?.data as T3 | undefined;
  const t4 = tierOf(data, "T4")?.data as { assessment?: string } | undefined;

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-[--color-text-primary]">
            All-Weather
          </h2>
          <SeverityPill severity={data.severity} />
          <FreshnessBadge generatedAt={data.generated_at} />
        </div>
        <div className="flex items-center gap-3">
          <SmartModeToggle value={smartMode} onChange={setSmartMode} />
        </div>
      </header>

      {t3?.portfolio_source === "fallback_60_40" ? (
        <div
          role="alert"
          className="rounded-[--radius-md] border border-[--color-feedback-warning] bg-[--color-bg-elevated] p-3 text-sm text-[--color-text-primary]"
          data-testid="fallback-banner"
        >
          No user portfolio found — showing analysis against a 60/40 fallback.
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Portfolio Comparison">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-[--color-text-tertiary]">
              <tr>
                <th className="text-left">Asset</th>
                <th className="text-right">You</th>
                <th className="text-right">Reference</th>
              </tr>
            </thead>
            <tbody className="text-[--color-text-primary]">
              {Object.keys(t3?.reference_allocation ?? {}).map((asset) => (
                <tr key={asset}>
                  <td>{asset}</td>
                  <td className="text-right font-mono">
                    {pct(t3?.portfolio?.[asset] ?? 0)}
                  </td>
                  <td className="text-right font-mono">
                    {pct(t3?.reference_allocation?.[asset] ?? 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Season Coverage">
          <div className="grid grid-cols-4 gap-2 text-center text-xs">
            {Object.entries(t3?.season_coverage ?? {}).map(([season, tier]) => (
              <div
                key={season}
                className={`rounded-[--radius-md] p-2 ${
                  COVERAGE_CELL[tier] ??
                  "bg-[--color-bg-base] text-[--color-text-primary]"
                }`}
              >
                <div className="text-[10px] uppercase opacity-80">{season}</div>
                <div className="mt-1 font-medium">{tier}</div>
              </div>
            ))}
          </div>
          <div className="mt-2 text-xs text-[--color-text-tertiary]">
            {t3?.overall_coverage_label ?? ""}
          </div>
        </Panel>

        <Panel title="Risk Parity">
          <ul className="space-y-1 text-sm">
            {Object.entries(t3?.risk_contributions ?? {}).map(([asset, rc]) => (
              <li key={asset} className="flex items-center gap-2">
                <span className="w-16 text-[--color-text-secondary]">
                  {asset}
                </span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-[--color-border-subtle]">
                  <div
                    className="absolute inset-y-0 left-0 bg-[--color-accent-primary]"
                    style={{ width: `${Math.min(100, rc * 100)}%` }}
                  />
                </div>
                <span className="w-14 text-right font-mono text-xs text-[--color-text-primary]">
                  {pct(rc)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Gold Gap">
          <div className="text-2xl font-semibold text-[--color-text-primary]">
            {typeof t3?.gold_gap === "number" ? pct(t3.gold_gap) : "—"}
          </div>
          <div className="mt-1 text-xs text-[--color-text-tertiary]">
            Gap to All-Weather reference gold weight.
          </div>
        </Panel>
      </div>

      <AssessmentBlock
        text={t4?.assessment ?? null}
        generatedAt={data.generated_at}
      />
      {smartMode ? (
        <div className="text-xs text-[--color-text-tertiary]">
          Smart Mode adjusts risk-parity target bands during regime stress.
        </div>
      ) : null}
    </section>
  );
}
