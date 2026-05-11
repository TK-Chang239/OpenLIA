import { useEffect, useState } from "react";

import { fetchTickerSeries, type TickerSeriesResponse } from "../api/portfolio";

/** Fetch one batch of per-ticker 1W daily closes for the active market.
 *  Used by HoldingsTable to render a 7D sparkline per row. */
export function useSparklines(market?: string): {
  readonly data: TickerSeriesResponse | null;
  readonly loading: boolean;
} {
  const [data, setData] = useState<TickerSeriesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchTickerSeries("1w", market)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [market]);

  return { data, loading } as const;
}
