import type { ChatSession } from "../../api/chat";
import type { ReportListItem } from "../../api/reports";

interface Props {
  session: ChatSession;
  attachedReport: ReportListItem | null;
  locked: boolean;
  lockMessage?: string;
}

const DEFAULT_LOCK_MESSAGE =
  "The report this discussion was about can no longer be fetched. I'm unable to answer any questions about it.";

export function ChatHeader({ session, attachedReport, locked, lockMessage }: Props): JSX.Element | null {
  if (locked) {
    return (
      <div className="banner banner--locked px-4 py-2 text-sm bg-status-warning/10 border-b border-status-warning/30 text-status-warning">
        {lockMessage ?? DEFAULT_LOCK_MESSAGE}
      </div>
    );
  }

  if (session.attached_report_id && attachedReport) {
    return (
      <div className="banner banner--attached-report flex items-center gap-2 px-4 py-2 text-sm bg-bg-elevated border-b border-border-subtle text-text-secondary">
        <span>Discussing report: {attachedReport.title}</span>
        <a
          href={`/reports/${attachedReport.id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-primary underline hover:opacity-80"
        >
          Open report
        </a>
      </div>
    );
  }

  return null;
}
