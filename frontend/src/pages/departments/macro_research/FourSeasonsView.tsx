import { useCallback, useEffect, useState } from "react";
import {
  getDashboard,
  type DashboardResult,
} from "../../../api/macro_research";
import {
  ErrorBlock,
  FreshnessBadge,
  LoadingBlock,
  Panel,
  SeverityPill,
  SmartModeToggle,
  tierOf,
} from "./DashboardFrame";

type T3 = {
  season?: string;
  confidence?: string;
  growth_axis?: string;
  inflation_axis?: string;
  credit_spread?: number;
  asset_playbook?: { best?: string[]; worst?: string[] };
};

export default function FourSeasonsView(): JSX.Element {
  const [data, setData] = useState<DashboardResult | null>(null);
  const [smartMode, setSmartMode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((sm: boolean) => {
    getDashboard("four_seasons", sm)
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
  if (!data) return <LoadingBlock label="Four Seasons" />;

  const t3 = tierOf(data, "T3")?.data as T3 | undefined;
  const playbook = t3?.asset_playbook ?? { best: [], worst: [] };

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-[--color-text-primary]">
            Four Seasons
          </h2>
          <SeverityPill severity={data.severity} />
          <FreshnessBadge generatedAt={data.generated_at} />
        </div>
        <div className="flex items-center gap-3">
          <SmartModeToggle value={smartMode} onChange={setSmartMode} />
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="Season">
          <div className="text-2xl font-semibold text-[--color-text-primary]">
            {t3?.season ?? "Unknown"}
          </div>
          <div className="mt-1 text-xs text-[--color-text-tertiary]">
            Confidence: {t3?.confidence ?? "—"}
          </div>
        </Panel>
        <Panel title="Growth / Inflation">
          <ul className="space-y-1 text-sm text-[--color-text-primary]">
            <li>Growth: {t3?.growth_axis ?? "—"}</li>
            <li>Inflation: {t3?.inflation_axis ?? "—"}</li>
            <li>
              Credit spread:{" "}
              <span className="font-mono">
                {typeof t3?.credit_spread === "number"
                  ? t3.credit_spread.toFixed(3)
                  : "—"}
              </span>
            </li>
          </ul>
        </Panel>
        <Panel title="Asset Playbook">
          <div className="space-y-2 text-sm">
            <div>
              <div className="text-xs uppercase text-[--color-feedback-success]">
                Best
              </div>
              <ul className="list-disc pl-4 text-[--color-text-primary]">
                {(playbook.best ?? []).map((x) => (
                  <li key={`b-${x}`}>{x}</li>
                ))}
                {(playbook.best ?? []).length === 0 ? <li>—</li> : null}
              </ul>
            </div>
            <div>
              <div className="text-xs uppercase text-[--color-feedback-error]">
                Worst
              </div>
              <ul className="list-disc pl-4 text-[--color-text-primary]">
                {(playbook.worst ?? []).map((x) => (
                  <li key={`w-${x}`}>{x}</li>
                ))}
                {(playbook.worst ?? []).length === 0 ? <li>—</li> : null}
              </ul>
            </div>
          </div>
        </Panel>
      </div>

      {smartMode ? (
        <div className="text-xs text-[--color-text-tertiary]">
          Smart Mode adjusts axis thresholds based on recent surprises.
        </div>
      ) : null}
    </section>
  );
}
