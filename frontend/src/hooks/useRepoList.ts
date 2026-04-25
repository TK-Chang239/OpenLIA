import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listRepoItemsFiltered,
  type RepoListParams,
  type RepoRow,
  type RepoSort,
} from "../api/repo";

const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 250;

const VALID_SORTS: ReadonlyArray<RepoSort> = [
  "saved_desc",
  "saved_asc",
  "generated_desc",
  "generated_asc",
  "department_asc",
  "filename_asc",
];

export interface RepoListState {
  q: string;
  departments: string[];
  generated_from: string;
  generated_to: string;
  saved_from: string;
  saved_to: string;
  sort: RepoSort;
}

export interface UseRepoListResult {
  rows: RepoRow[];
  hasMore: boolean;
  loading: boolean;
  error: string | null;
  page: number;
  loadMore: () => void;
  sentinelRef: (node: Element | null) => void;
  params: RepoListState;
  setParams: (next: Partial<RepoListState>) => void;
  clearFilters: () => void;
  removeRow: (rowId: string) => RepoRow | undefined;
  restoreRow: (row: RepoRow, atIndex?: number) => void;
}

function parseSort(raw: string | null): RepoSort {
  if (raw && (VALID_SORTS as readonly string[]).includes(raw)) return raw as RepoSort;
  return "saved_desc";
}

function readState(sp: URLSearchParams): RepoListState {
  return {
    q: sp.get("q") ?? "",
    departments: (sp.getAll("department").length > 0
      ? sp.getAll("department").flatMap((v) => v.split(",")).filter(Boolean)
      : []) as string[],
    generated_from: sp.get("generated_from") ?? "",
    generated_to: sp.get("generated_to") ?? "",
    saved_from: sp.get("saved_from") ?? "",
    saved_to: sp.get("saved_to") ?? "",
    sort: parseSort(sp.get("sort")),
  };
}

function writeState(state: RepoListState): URLSearchParams {
  const sp = new URLSearchParams();
  if (state.q) sp.set("q", state.q);
  if (state.departments.length > 0) {
    for (const d of state.departments) sp.append("department", d);
  }
  if (state.generated_from) sp.set("generated_from", state.generated_from);
  if (state.generated_to) sp.set("generated_to", state.generated_to);
  if (state.saved_from) sp.set("saved_from", state.saved_from);
  if (state.saved_to) sp.set("saved_to", state.saved_to);
  if (state.sort && state.sort !== "saved_desc") sp.set("sort", state.sort);
  return sp;
}

export function useRepoList(): UseRepoListResult {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => readState(searchParams), [searchParams]);

  const [debouncedQ, setDebouncedQ] = useState<string>(params.q);
  const [rows, setRows] = useState<RepoRow[]>([]);
  const [page, setPage] = useState<number>(1);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const reqIdRef = useRef<number>(0);

  // Debounce q.
  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedQ(params.q), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [params.q]);

  const setParams = useCallback(
    (next: Partial<RepoListState>) => {
      setSearchParams(
        (prev) => {
          const merged = { ...readState(prev), ...next } as RepoListState;
          return writeState(merged);
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => {
    setSearchParams(new URLSearchParams(), { replace: true });
  }, [setSearchParams]);

  const fetchPage = useCallback(
    async (pageNum: number, reset: boolean, query: RepoListParams) => {
      const reqId = ++reqIdRef.current;
      setLoading(true);
      setError(null);
      try {
        const body = await listRepoItemsFiltered({
          ...query,
          page: pageNum,
          page_size: PAGE_SIZE,
        });
        if (reqId !== reqIdRef.current) return;
        setHasMore(body.has_more);
        setRows((prev) => (reset ? body.items : [...prev, ...body.items]));
        setPage(pageNum);
      } catch (e) {
        if (reqId !== reqIdRef.current) return;
        setError(e instanceof Error ? e.message : "Failed to load saved reports");
      } finally {
        if (reqId === reqIdRef.current) setLoading(false);
      }
    },
    [],
  );

  // Reset+fetch on params change (debounced q + others).
  useEffect(() => {
    void fetchPage(1, true, {
      q: debouncedQ || undefined,
      departments: params.departments.length > 0 ? params.departments : undefined,
      generated_from: params.generated_from || undefined,
      generated_to: params.generated_to || undefined,
      saved_from: params.saved_from || undefined,
      saved_to: params.saved_to || undefined,
      sort: params.sort,
    });
  }, [
    debouncedQ,
    params.departments,
    params.generated_from,
    params.generated_to,
    params.saved_from,
    params.saved_to,
    params.sort,
    fetchPage,
  ]);

  const loadMore = useCallback(() => {
    if (loading || !hasMore) return;
    void fetchPage(page + 1, false, {
      q: debouncedQ || undefined,
      departments: params.departments.length > 0 ? params.departments : undefined,
      generated_from: params.generated_from || undefined,
      generated_to: params.generated_to || undefined,
      saved_from: params.saved_from || undefined,
      saved_to: params.saved_to || undefined,
      sort: params.sort,
    });
  }, [loading, hasMore, page, debouncedQ, params, fetchPage]);

  // IntersectionObserver sentinel.
  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useCallback(
    (node: Element | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      if (!node) return;
      if (typeof IntersectionObserver === "undefined") return;
      const obs = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              loadMore();
            }
          }
        },
        { rootMargin: "200px" },
      );
      obs.observe(node);
      observerRef.current = obs;
    },
    [loadMore],
  );

  useEffect(() => () => observerRef.current?.disconnect(), []);

  const removeRow = useCallback(
    (rowId: string): RepoRow | undefined => {
      let removed: RepoRow | undefined;
      setRows((prev) => {
        const idx = prev.findIndex((r) => r.id === rowId);
        if (idx < 0) return prev;
        removed = prev[idx];
        return prev.filter((r) => r.id !== rowId);
      });
      return removed;
    },
    [],
  );

  const restoreRow = useCallback((row: RepoRow, atIndex?: number) => {
    setRows((prev) => {
      const next = [...prev];
      const idx = atIndex !== undefined && atIndex >= 0 ? Math.min(atIndex, next.length) : 0;
      next.splice(idx, 0, row);
      return next;
    });
  }, []);

  return {
    rows,
    hasMore,
    loading,
    error,
    page,
    loadMore,
    sentinelRef,
    params,
    setParams,
    clearFilters,
    removeRow,
    restoreRow,
  };
}
