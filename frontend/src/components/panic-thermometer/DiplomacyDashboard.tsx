import type { PanelResult } from "../../api/panic-thermometer";

interface Props {
  result: PanelResult | undefined;
  onMarkMilestone?: () => void;
}

export function DiplomacyDashboard({ result, onMarkMilestone }: Props): JSX.Element {
  const daysElapsed = Number(result?.extras?.days_elapsed ?? 0);
  const daysRemaining = Number(result?.extras?.days_remaining ?? 0);
  const windowDays = Number(result?.resolved_values?.window_days ?? 30);
  const pct = Math.min(100, Math.max(0, (daysElapsed / Math.max(1, windowDays)) * 100));
  const progress = (result?.extras?.matched_progress_headlines as string[] | undefined) ?? [];
  const escalation =
    (result?.extras?.matched_escalation_headlines as string[] | undefined) ?? [];

  return (
    <div data-testid="diplomacy-dashboard">
      <h4>Diplomatic Progress</h4>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div>
          <div style={{ fontSize: "0.85rem" }}>
            Day {daysElapsed} of {windowDays} ({daysRemaining} remaining)
          </div>
          <div
            data-testid="diplomacy-progress"
            style={{
              width: "100%",
              height: 12,
              background: "var(--color-border-subtle)",
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${pct}%`,
                height: "100%",
                background:
                  pct >= 100
                    ? "var(--color-feedback-error)"
                    : pct >= 50
                      ? "var(--color-feedback-warning)"
                      : "var(--color-feedback-success)",
              }}
            />
          </div>
        </div>
        <button
          type="button"
          data-testid="diplomacy-mark-milestone"
          onClick={onMarkMilestone}
        >
          Mark milestone
        </button>
        <section>
          <strong>Progress signals ({progress.length})</strong>
          <ul>
            {progress.map((h, i) => (
              <li key={`p-${i}`}>{h}</li>
            ))}
          </ul>
        </section>
        <section>
          <strong>Escalation signals ({escalation.length})</strong>
          <ul>
            {escalation.map((h, i) => (
              <li key={`e-${i}`}>{h}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
