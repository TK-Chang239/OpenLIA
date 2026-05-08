import type { RsSpike } from "../../api/retail-sentiment";

interface Props {
  spike: RsSpike;
  onPick?: (ticker: string) => void;
}

export function SignalAlert({ spike, onPick }: Props) {
  const tone =
    spike.z_score > 3
      ? "var(--color-feedback-error)"
      : "var(--color-feedback-warning)";
  const captured = new Date(spike.detected_at);
  return (
    <button
      type="button"
      onClick={() => onPick?.(spike.ticker)}
      data-testid={`signal-${spike.ticker}`}
      className="rs-col-card text-left p-4 w-full"
      style={{
        borderRadius: "10px",
        borderColor: tone,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2">
          <span
            className="rs-mono-label"
            style={{ color: tone, letterSpacing: "0.16em" }}
          >
            BUZZ SPIKE
          </span>
          <span
            className="font-mono font-semibold tracking-[0.02em] text-[--color-text-primary]"
            style={{ fontSize: "14px" }}
          >
            {spike.ticker}
          </span>
        </span>
        <span className="rs-mono-value text-[12px]" style={{ color: tone }}>
          z = {spike.z_score.toFixed(2)}
        </span>
      </div>
      <div className="rs-mono-label mt-2 flex flex-wrap gap-4">
        <span>
          today {spike.buzz.toFixed(0)}
        </span>
        <span>μ {spike.baseline_mean.toFixed(1)}</span>
        <span>σ {spike.baseline_stddev.toFixed(1)}</span>
        <span>{captured.toLocaleString()}</span>
      </div>
    </button>
  );
}
