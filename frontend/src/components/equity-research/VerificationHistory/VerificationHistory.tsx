export interface VerifierIssue {
  issue_type: string;
  section_id?: string | null;
  severity: "blocker" | "warning";
  evidence: string;
  suggested_fix?: string | null;
  detector: "deterministic" | "llm";
}

export interface VerificationHistoryEntry {
  issue: VerifierIssue;
  raised_at_round: number;
  final_resolution:
    | "resolved"
    | "persisted_degraded"
    | "persisted_failed"
    | "still_open";
  resolved_in_round?: number | null;
}

export interface VerificationHistoryData {
  entries: VerificationHistoryEntry[];
  total_issues_raised?: number;
  resolved_on_first_retry?: number;
  resolved_on_subsequent_retry?: number;
  persisted_to_degraded?: number;
  warnings_open?: number;
}

interface Props {
  history: VerificationHistoryData;
  devMode: boolean;
}

const RESOLUTION_CLASS: Record<
  VerificationHistoryEntry["final_resolution"],
  string
> = {
  resolved: "resolution-resolved",
  persisted_degraded: "resolution-persisted_degraded",
  persisted_failed: "resolution-persisted_failed",
  still_open: "resolution-still_open",
};

export function VerificationHistory({ history, devMode }: Props) {
  if (!devMode) return null;

  const total = history.total_issues_raised ?? history.entries.length;

  return (
    <section
      id="verification_history"
      className="dev-only verification-history"
    >
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-lg font-semibold text-[--color-text-primary]">
          Verification History
        </h2>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-[--color-surface-hover] text-[--color-text-tertiary] border border-[--color-border-subtle]">
          DEV
        </span>
      </div>

      <p className="text-sm text-[--color-text-secondary] mb-4">
        {total} issue{total !== 1 ? "s" : ""} raised
        {history.resolved_on_first_retry != null &&
          ` · ${history.resolved_on_first_retry} resolved on first retry`}
        {history.resolved_on_subsequent_retry != null &&
          ` · ${history.resolved_on_subsequent_retry} on subsequent`}
        {history.persisted_to_degraded != null &&
          ` · ${history.persisted_to_degraded} persisted degraded`}
        {history.warnings_open != null &&
          ` · ${history.warnings_open} warnings open`}
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-[--color-text-tertiary] text-xs uppercase tracking-wider border-b border-[--color-border-subtle]">
              <th className="pb-2 pr-3 font-medium">Section</th>
              <th className="pb-2 pr-3 font-medium">Issue</th>
              <th className="pb-2 pr-3 font-medium">Severity</th>
              <th className="pb-2 pr-3 font-medium">Detector</th>
              <th className="pb-2 pr-3 font-medium">Resolution</th>
              <th className="pb-2 font-medium">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {history.entries.map((entry, i) => (
              <tr
                key={i}
                className={`border-b border-[--color-border-subtle] last:border-0 ${RESOLUTION_CLASS[entry.final_resolution]}`}
              >
                <td className="py-2 pr-3 font-mono text-xs text-[--color-text-tertiary]">
                  {entry.issue.section_id ?? "—"}
                </td>
                <td className="py-2 pr-3 text-[--color-text-primary]">
                  {entry.issue.issue_type}
                </td>
                <td className="py-2 pr-3">
                  <span
                    className={
                      entry.issue.severity === "blocker"
                        ? "text-[--color-feedback-error] font-mono text-xs"
                        : "text-[--color-feedback-warning] font-mono text-xs"
                    }
                  >
                    {entry.issue.severity}
                  </span>
                </td>
                <td className="py-2 pr-3 font-mono text-xs text-[--color-text-tertiary]">
                  {entry.issue.detector}
                </td>
                <td className="py-2 pr-3 font-mono text-xs text-[--color-text-secondary]">
                  {entry.final_resolution}
                </td>
                <td className="py-2 text-[--color-text-secondary] text-xs max-w-xs truncate">
                  {entry.issue.evidence}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
