import { useCallback, useEffect, useState } from "react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

export type FetchStatus = "loading" | "loaded" | "error" | "empty";

export interface FileFetchResult<T> {
  status: FetchStatus;
  data: T | null;
  error: Error | null;
  retry: () => void;
}

interface Options<T> {
  parse: (raw: string) => T;
  /** Optional `(parsed) => boolean` predicate; true means treat as empty. */
  isEmpty?: (parsed: T) => boolean;
}

export function useFileFetch<T = string>(
  source: FileSource,
  options: Options<T> = { parse: (raw) => raw as unknown as T },
): FileFetchResult<T> {
  const [status, setStatus] = useState<FetchStatus>("loading");
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  const url = sourceUrl(source);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);
    fetch(url, { credentials: "same-origin" })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then((raw) => {
        if (cancelled) return;
        if (!raw || raw.trim().length === 0) {
          setData(null);
          setStatus("empty");
          return;
        }
        try {
          const parsed = options.parse(raw);
          if (options.isEmpty?.(parsed)) {
            setData(parsed);
            setStatus("empty");
            return;
          }
          setData(parsed);
          setStatus("loaded");
        } catch (err) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setStatus("error");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // tick is the explicit retry trigger; options.parse intentionally
    // omitted to avoid re-fetching when callers pass an inline lambda.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, tick]);

  const retry = useCallback(() => setTick((t) => t + 1), []);

  return { status, data, error, retry };
}
