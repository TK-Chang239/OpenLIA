import type { RsSpike } from "../../api/retail-sentiment";

interface Props {
  spike: RsSpike;
}

export function SignalAlert({ spike }: Props) {
  return (
    <div
      data-testid={`signal-${spike.ticker}`}
      className="rounded-md border border-[--color-feedback-error] bg-[--color-feedback-error-bg] p-3"
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-[--color-text-primary]">
          {spike.ticker} — buzz spike
        </span>
        <span className="text-xs uppercase text-[--color-feedback-error]">
          z={spike.z_score.toFixed(2)}
        </span>
      </div>
      <div className="mt-1 text-xs text-[--color-text-secondary]">
        Today {spike.buzz.toFixed(0)} vs baseline μ={spike.baseline_mean.toFixed(1)} σ=
        {spike.baseline_stddev.toFixed(1)}
      </div>
    </div>
  );
}
