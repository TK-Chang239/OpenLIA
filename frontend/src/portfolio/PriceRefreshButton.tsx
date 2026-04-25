import { RefreshCw } from "lucide-react";
import { useState } from "react";

export interface PriceRefreshButtonProps {
  readonly onRefresh: () => Promise<void>;
  readonly onSuccess?: () => void;
  readonly onRateLimited?: (seconds: number) => void;
}

export function PriceRefreshButton({
  onRefresh,
  onSuccess,
  onRateLimited,
}: PriceRefreshButtonProps): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const click = async () => {
    setBusy(true);
    setError(null);
    try {
      await onRefresh();
      onSuccess?.();
    } catch (e) {
      const err = e as Error & { retryAfter?: number; status?: number };
      if (err.status === 429 && err.retryAfter) {
        const msg = `Try again in ${err.retryAfter} seconds`;
        setError(msg);
        onRateLimited?.(err.retryAfter);
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="inline-flex flex-col gap-1" data-testid="price-refresh">
      <button
        type="button"
        onClick={() => void click()}
        disabled={busy}
        className="inline-flex items-center gap-2 px-3 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] hover:bg-[--color-surface-hover]"
        data-testid="price-refresh-btn"
      >
        <RefreshCw size={14} aria-hidden="true" className={busy ? "animate-spin" : ""} />
        Refresh prices
      </button>
      {error ? (
        <span className="text-xs text-[--color-feedback-error]" data-testid="price-refresh-error">
          {error}
        </span>
      ) : null}
    </div>
  );
}
