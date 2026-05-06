import type { JSX } from "react";
import { departmentLabel } from "../../lib/department-colors";

interface Props {
  /** Department slug (e.g., "secretary", "equity_research"). */
  departmentId?: string | null;
  /** Total tokens used by the response. Hidden when null/0. */
  tokens?: number | null;
  /** Wall-clock latency from first stream event to `done`, in milliseconds.
   *  Hidden when null. */
  latencyMs?: number | null;
}

function formatTokens(n: number): string {
  if (n >= 1000) {
    const k = n / 1000;
    return `${k.toFixed(k >= 10 ? 0 : 1)}k`;
  }
  return n.toLocaleString();
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Small mono tag rendered above an assistant message bubble:
 *
 *     • Equity Research · 1,284 tokens · 2.1s
 *
 * Pieces are dropped when the corresponding data is unavailable. */
export function AssistantMessageTag({
  departmentId,
  tokens,
  latencyMs,
}: Props): JSX.Element | null {
  const parts: string[] = [];
  if (departmentId) parts.push(departmentLabel(departmentId));
  if (tokens && tokens > 0) parts.push(`${formatTokens(tokens)} tokens`);
  if (latencyMs && latencyMs > 0) parts.push(formatLatency(latencyMs));
  if (parts.length === 0) return null;

  return (
    <span
      className="mb-2 inline-flex items-center gap-[6px] font-mono text-[9px] uppercase"
      style={{
        letterSpacing: "var(--tracking-micro)",
        color: "var(--color-text-tertiary)",
      }}
    >
      <span
        aria-hidden="true"
        className="inline-block w-1 h-1 rounded-full"
        style={{ background: "var(--color-accent-primary)" }}
      />
      {parts.join(" · ")}
    </span>
  );
}
