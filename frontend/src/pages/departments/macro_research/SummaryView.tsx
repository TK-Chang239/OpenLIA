import { Link } from "react-router-dom";
import type { DashboardSummary } from "../../../api/macro_research";

export default function SummaryView({
  dashboards,
}: {
  dashboards: DashboardSummary[];
}): JSX.Element {
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
        {dashboards.map((d) => (
          <li key={d.slug}>
            <Link
              to={d.slug}
              className="block rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4 transition hover:border-[--color-accent-primary]"
            >
              <div className="text-base font-medium text-[--color-text-primary]">
                {d.display_name}
              </div>
              <div className="mt-1 text-xs text-[--color-text-tertiary]">
                Open dashboard →
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
