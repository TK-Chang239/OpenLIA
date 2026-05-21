export interface TaskOutcome {
  task_type: string;
  task_name: string;
  status: "OK" | "SKIPPED" | "DEGRADED" | "FAILED";
  notes?: string;
  duration_ms: number;
}

export interface RunSummaryData {
  engine_version: string;
  template_id: string;
  template_name: string;
  composer_inputs: Record<string, unknown>;
  outcomes: TaskOutcome[];
  unsupported_requests_dismissed: string[];
  unsupported_requests_slipped: string[];
  total_duration_ms: number;
  total_token_cost?: number;
  cache_stats: Record<string, { hits: number; misses: number }>;
}

interface Props {
  summary: RunSummaryData;
}

const STATUS_CLASS: Record<TaskOutcome["status"], string> = {
  OK: "status-ok",
  SKIPPED: "status-skipped",
  DEGRADED: "status-degraded",
  FAILED: "status-failed",
};

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export function RunSummary({ summary }: Props) {
  const hasCacheStats = Object.keys(summary.cache_stats).length > 0;

  return (
    <section id="run_summary" className="run-summary">
      <h2 className="text-lg font-semibold text-[--color-text-primary] mb-3">
        Run Summary
      </h2>

      <p className="text-sm text-[--color-text-secondary] mb-4 font-mono">
        Engine v{summary.engine_version}
        {" · "}
        {summary.template_name}
        {" · "}
        {formatMs(summary.total_duration_ms)}
        {summary.total_token_cost != null && (
          <>{" · "}{summary.total_token_cost.toLocaleString()} tokens</>
        )}
      </p>

      <div className="mb-6 overflow-x-auto">
        <table className="run-summary-outcomes w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-[--color-text-tertiary] text-xs uppercase tracking-wider border-b border-[--color-border-subtle]">
              <th className="pb-2 pr-4 font-medium">Type</th>
              <th className="pb-2 pr-4 font-medium">Task</th>
              <th className="pb-2 pr-4 font-medium">Status</th>
              <th className="pb-2 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            {summary.outcomes.map((outcome, i) => (
              <tr
                key={i}
                className={`border-b border-[--color-border-subtle] last:border-0 ${STATUS_CLASS[outcome.status]}`}
              >
                <td className="py-2 pr-4 font-mono text-xs text-[--color-text-tertiary]">
                  {outcome.task_type}
                </td>
                <td className="py-2 pr-4 text-[--color-text-primary]">
                  {outcome.task_name}
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={
                      outcome.status === "OK"
                        ? "text-[--color-feedback-success] font-mono text-xs"
                        : outcome.status === "SKIPPED"
                          ? "text-[--color-text-tertiary] font-mono text-xs"
                          : outcome.status === "DEGRADED"
                            ? "text-[--color-feedback-warning] font-mono text-xs"
                            : "text-[--color-feedback-error] font-mono text-xs"
                    }
                  >
                    {outcome.status}
                  </span>
                </td>
                <td className="py-2 text-[--color-text-secondary] text-xs">
                  {outcome.notes ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mb-4">
        <h3 className="text-sm font-medium text-[--color-text-primary] mb-2">
          Requests not fulfilled
        </h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wider text-[--color-text-tertiary] mb-1">
              Acknowledged
            </p>
            <ul className="list-disc list-inside text-[--color-text-secondary] space-y-1">
              {summary.unsupported_requests_dismissed.length === 0 ? (
                <li className="text-[--color-text-tertiary]">(none)</li>
              ) : (
                summary.unsupported_requests_dismissed.map((req, i) => (
                  <li key={i}>{req}</li>
                ))
              )}
            </ul>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-[--color-text-tertiary] mb-1">
              Detected at runtime
            </p>
            <ul className="list-disc list-inside text-[--color-text-secondary] space-y-1">
              {summary.unsupported_requests_slipped.length === 0 ? (
                <li className="text-[--color-text-tertiary]">(none)</li>
              ) : (
                summary.unsupported_requests_slipped.map((req, i) => (
                  <li key={i}>{req}</li>
                ))
              )}
            </ul>
          </div>
        </div>
      </div>

      {hasCacheStats && (
        <div>
          <h3 className="text-sm font-medium text-[--color-text-primary] mb-2">
            Cache stats
          </h3>
          <table className="w-full text-xs border-collapse font-mono">
            <thead>
              <tr className="text-left text-[--color-text-tertiary] border-b border-[--color-border-subtle]">
                <th className="pb-1 pr-4 font-medium">Source</th>
                <th className="pb-1 pr-4 font-medium">Hits</th>
                <th className="pb-1 font-medium">Misses</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.cache_stats).map(([source, stats]) => (
                <tr key={source} className="border-b border-[--color-border-subtle] last:border-0">
                  <td className="py-1 pr-4 text-[--color-text-secondary]">{source}</td>
                  <td className="py-1 pr-4 text-[--color-feedback-success]">{stats.hits}</td>
                  <td className="py-1 text-[--color-text-tertiary]">{stats.misses}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
