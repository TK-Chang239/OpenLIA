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
import { listRepoItems } from "../../api/repo";

interface ContextShape {
  isSaved: (reportId: string) => boolean;
  markSaved: (reportId: string) => void;
  markUnsaved: (reportId: string) => void;
}

const SavedReportsContext = createContext<ContextShape | null>(null);

export function SavedReportsProvider({ children }: { children: ReactNode }): JSX.Element {
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    let cancelled = false;
    void listRepoItems()
      .then((res) => {
        if (cancelled) return;
        setSavedIds(new Set(res.items.map((i) => i.report_id)));
      })
      .catch(() => {
        // Hydration is best-effort; individual buttons still work via local state.
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

  const value = useMemo<ContextShape>(
    () => ({ isSaved, markSaved, markUnsaved }),
    [isSaved, markSaved, markUnsaved],
  );

  return <SavedReportsContext.Provider value={value}>{children}</SavedReportsContext.Provider>;
}

export function useSavedReportsOptional(): ContextShape | null {
  return useContext(SavedReportsContext);
}
