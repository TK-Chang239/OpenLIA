import { RS_METRIC_CATALOG } from "../../lib/retail-sentiment/metric-catalog";
import { ReliabilityBadge } from "./ReliabilityBadge";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function MetricsDeepDive({ open, onClose }: Props) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-label="Metrics deep dive"
      data-testid="metrics-deep-dive"
      className="fixed inset-y-0 right-0 z-40 flex w-[480px] max-w-full flex-col border-l border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-2xl"
    >
      <header className="flex items-center justify-between border-b border-[--color-border-subtle] px-4 py-3">
        <h2 className="text-sm font-semibold">Metrics deep dive</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close metrics deep dive"
          className="rounded-md border border-[--color-border-secondary] px-2 py-1 text-xs"
        >
          Close
        </button>
      </header>
      <div className="space-y-3 overflow-y-auto p-4">
        {RS_METRIC_CATALOG.map((m) => (
          <section
            key={m.id}
            className="rounded-md border border-[--color-border-subtle] p-3"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                {m.number}. {m.label}
              </h3>
              <ReliabilityBadge tier={m.reliability} />
            </div>
            <p className="mt-1 text-xs text-[--color-text-secondary]">
              {m.description}
            </p>
            <p className="mt-1 font-mono text-xs">
              <span className="text-[--color-text-secondary]">Formula:</span>{" "}
              {m.formula}
            </p>
            <p className="mt-1 text-xs">
              <span className="text-[--color-text-secondary]">Units:</span>{" "}
              {m.units}
            </p>
          </section>
        ))}
      </div>
    </div>
  );
}
