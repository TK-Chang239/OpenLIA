import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type JSX,
  type ReactNode,
} from "react";
import { listRepoItems, listSavedV2Runs } from "../../api/repo";

interface ContextShape {
  // v1 reports — keyed by reports.id.
  isSaved: (reportId: string) => boolean;
  markSaved: (reportId: string) => void;
  markUnsaved: (reportId: string) => void;
  // v2.2 pipeline_runs — keyed by pipeline_runs.id. Kept in a separate
  // set because the id namespaces never overlap and the engines may have
  // both saved at once.
  isV2Saved: (runId: string) => boolean;
  markV2Saved: (runId: string) => void;
  markV2Unsaved: (runId: string) => void;
}

const SavedReportsContext = createContext<ContextShape | null>(null);

export function SavedReportsProvider({ children }: { children: ReactNode }): JSX.Element {
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());
  const [savedV2Ids, setSavedV2Ids] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    let cancelled = false;
    void listRepoItems()
      .then((res) => {
        if (cancelled) return;
        // v1 rows return report_id; v2 rows leave it null. Filter for safety.
        const v1Ids = res.items
          .map((i) => i.report_id)
          .filter((x): x is string => typeof x === "string" && x.length > 0);
        setSavedIds(new Set(v1Ids));
      })
      .catch(() => {
        // Hydration is best-effort; individual buttons still work via local state.
      });
    void listSavedV2Runs()
      .then((res) => {
        if (cancelled) return;
        setSavedV2Ids(new Set(res.saved_run_ids));
      })
      .catch(() => {
        // Endpoint is new — older deployments will 404; that's fine.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isSaved = useCallback((reportId: string) => savedIds.has(reportId), [savedIds]);

  const markSaved = useCallback((reportId: string) => {
    setSavedIds((prev) => {
      if (prev.has(reportId)) return prev;
      const next = new Set(prev);
      next.add(reportId);
      return next;
    });
  }, []);

  const markUnsaved = useCallback((reportId: string) => {
    setSavedIds((prev) => {
      if (!prev.has(reportId)) return prev;
      const next = new Set(prev);
      next.delete(reportId);
      return next;
    });
  }, []);

  const isV2Saved = useCallback((runId: string) => savedV2Ids.has(runId), [savedV2Ids]);

  const markV2Saved = useCallback((runId: string) => {
    setSavedV2Ids((prev) => {
      if (prev.has(runId)) return prev;
      const next = new Set(prev);
      next.add(runId);
      return next;
    });
  }, []);

  const markV2Unsaved = useCallback((runId: string) => {
    setSavedV2Ids((prev) => {
      if (!prev.has(runId)) return prev;
      const next = new Set(prev);
      next.delete(runId);
      return next;
    });
  }, []);

  const value = useMemo<ContextShape>(
    () => ({
      isSaved,
      markSaved,
      markUnsaved,
      isV2Saved,
      markV2Saved,
      markV2Unsaved,
    }),
    [isSaved, markSaved, markUnsaved, isV2Saved, markV2Saved, markV2Unsaved],
  );

  return <SavedReportsContext.Provider value={value}>{children}</SavedReportsContext.Provider>;
}

export function useSavedReportsOptional(): ContextShape | null {
  return useContext(SavedReportsContext);
}
