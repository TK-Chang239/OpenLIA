import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { useDeptHealth } from "../../store/dept-health";

interface Props {
  departmentId: string;
}

/**
 * Renders an info banner above a department page when the dept is
 * currently disabled per the dept-health cache. Returns `null` when
 * the dept is active (or unknown), so callers can mount this
 * unconditionally above existing page content.
 */
export function DeptDisabledBanner({ departmentId }: Props) {
  const health = useDeptHealth((s) => s.healths[departmentId]);
  if (!health || health.status !== "disabled") return null;
  return (
    <div
      role="status"
      data-testid={`dept-disabled-banner-${departmentId}`}
      className="flex items-center gap-3 border-b border-feedback-warning/30 bg-feedback-warning/10 px-4 py-2 text-sm text-feedback-warning"
    >
      <AlertTriangle size={16} aria-hidden="true" />
      <p className="flex-1">
        This department is disabled.
        {health.reason ? <span className="ml-1">{health.reason}.</span> : null}
      </p>
      <Link
        to="/settings/connectors"
        className="text-sm font-medium underline hover:no-underline"
      >
        Settings &rarr; Connectors
      </Link>
    </div>
  );
}
