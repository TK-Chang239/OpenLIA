import { useCallback, useEffect, useState } from "react";

import type { PerfRange } from "./PortfolioPageHeader";

export interface ValueSeriesPoint {
  date: string;
  value: string;
}

export interface ActualSpan {
  start: string;
  end: string;
}

export interface ValueSeriesResponse {
  timeframe: string;
  actual_span: ActualSpan | null;
  points: ValueSeriesPoint[];
  period_return_abs: string | null;
  period_return_pct: string | null;
}

const RANGE_TO_PARAM: Record<PerfRange, string> = {
  "1D": "1d",
  "1W": "1w",
  "1M": "1m",
  "3M": "3m",
  "6M": "6m",
  YTD: "ytd",
  "1Y": "1y",
  "5Y": "5y",
};

async function fetchValueSeries(range: PerfRange): Promise<ValueSeriesResponse> {
  const tf = RANGE_TO_PARAM[range] ?? "1m";
  const res = await fetch(`/api/portfolio/value-series?timeframe=${tf}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`value-series: ${res.status}`);
  return (await res.json()) as ValueSeriesResponse;
}

/** Subscribe to the portfolio value series for the picker-selected range.
 *  Re-fetches on range change. */
export function useValueSeries(range: PerfRange): {
  readonly series: ValueSeriesResponse | null;
  readonly loading: boolean;
} {
  const [series, setSeries] = useState<ValueSeriesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setSeries(await fetchValueSeries(range));
    } catch {
      setSeries(null);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { series, loading } as const;
}
