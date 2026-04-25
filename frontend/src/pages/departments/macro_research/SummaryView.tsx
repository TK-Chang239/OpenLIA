import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getDashboard,
  type DashboardResult,
  type DashboardSummary,
} from "../../../api/macro_research";
import { FreshnessBadge, SeverityPill } from "./DashboardFrame";

interface RowState {
  slug: string;
  display_name: string;
  result: DashboardResult | null;
  error: string | null;
}

function topT3Line(result: DashboardResult | null): string | null {
  if (!result) return null;
  const t3 = result.tiers.find((t) => t.tier === "T3");
  if (!t3) return null;
  const data = t3.data as Record<string, unknown>;
  for (const k of [
    "phase",
    "season",
    "wealth_shift_stage",
    "overall_coverage_label",
    "bucket",
  ]) {
    const v = data[k];
    if (typeof v === "string" && v.length > 0) return v;
  }
  return null;
}

export default function SummaryView({
  dashboards,
}: {
  dashboards: DashboardSummary[];
}): JSX.Element {
  const [rows, setRows] = useState<RowState[]>(() =>
    dashboards.map((d) => ({
      slug: d.slug,
      display_name: d.display_name,
      result: null,
      error: null,
    })),
  );

  useEffect(() => {
    let cancelled = false;
    const initial = dashboards.map((d) => ({
      slug: d.slug,
      display_name: d.display_name,
      result: null as DashboardResult | null,
      error: null as string | null,
    }));
    setRows(initial);
    Promise.all(
      dashboards.map((d) =>
        getDashboard(d.slug)
          .then((r) => ({ slug: d.slug, result: r, error: null }))
          .catch((e: unknown) => ({
            slug: d.slug,
            result: null,
            error: String(e),
          })),
      ),
    ).then((results) => {
      if (cancelled) return;
      setRows((prev) =>
        prev.map((row) => {
          const match = results.find((r) => r.slug === row.slug);
          return match
            ? { ...row, result: match.result, error: match.error }
            : row;
        }),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [dashboards]);

  return (
    <section data-testid="mr-summary-view" className="space-y-4">
      <header>
        <h2 className="text-xl font-semibold text-[--color-text-primary]">
          Macro Research
        </h2>
        <p className="mt-1 text-sm text-[--color-text-secondary]">
          Dalio-inspired dashboards tracking debt cycles, growth/inflation
          regimes, portfolio balance, world-order wealth shifts, and structural
          change forces.
        </p>
      </header>
      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((row) => {
          const result = row.result;
          const t3line = topT3Line(result);
          const lastAt = result?.generated_at
            ? new Date(result.generated_at).toLocaleString()
            : null;
          return (
            <li key={row.slug}>
              <Link
                to={row.slug}
                data-testid={`summary-card-${row.slug}`}
                className="block rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4 transition hover:border-[--color-accent-primary]"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-base font-medium text-[--color-text-primary]">
                    {row.display_name}
                  </div>
                  {result ? (
                    <SeverityPill severity={result.severity} />
                  ) : null}
                </div>
                <div className="mt-2 flex items-center gap-2">
                  {result ? (
                    <FreshnessBadge generatedAt={result.generated_at} />
                  ) : null}
                  {lastAt ? (
                    <span
                      data-testid={`summary-last-at-${row.slug}`}
                      className="text-[11px] text-[--color-text-tertiary]"
                    >
                      {lastAt}
                    </span>
                  ) : null}
                </div>
                {t3line ? (
                  <div className="mt-2 text-xs text-[--color-text-secondary]">
                    {t3line}
                  </div>
                ) : null}
                {row.error ? (
                  <div className="mt-2 text-xs text-[--color-feedback-error]">
                    {row.error}
                  </div>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
