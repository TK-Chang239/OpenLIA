import { useTranslation } from "react-i18next";

import type { RsSpike } from "../../api/retail-sentiment";

interface Props {
  spike: RsSpike;
  onPick?: (ticker: string) => void;
}

export function SignalAlert({ spike, onPick }: Props) {
  const { t } = useTranslation();
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
            {t("retail_sentiment.signal_alert.buzz_spike")}
          </span>
          <span
            className="font-mono font-semibold tracking-[0.02em] text-[--color-text-primary]"
            style={{ fontSize: "14px" }}
          >
            {spike.ticker}
          </span>
        </span>
        <span className="rs-mono-value text-[12px]" style={{ color: tone }}>
          {t("retail_sentiment.signal_alert.z_prefix")} {spike.z_score.toFixed(2)}
        </span>
      </div>
      <div className="rs-mono-label mt-2 flex flex-wrap gap-4">
        <span>
          {t("retail_sentiment.signal_alert.today_prefix")} {spike.buzz.toFixed(0)}
        </span>
        <span>
          {t("retail_sentiment.signal_alert.mu_prefix")} {spike.baseline_mean.toFixed(1)}
        </span>
        <span>
          {t("retail_sentiment.signal_alert.sigma_prefix")} {spike.baseline_stddev.toFixed(1)}
        </span>
        <span>{captured.toLocaleString()}</span>
      </div>
    </button>
  );
}
