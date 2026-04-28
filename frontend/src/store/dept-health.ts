import { create } from "zustand";
import { fetchDeptHealth, type DepartmentHealth } from "../api/dept-health";

interface DeptHealthState {
  healths: Record<string, DepartmentHealth>;
  loaded: boolean;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export const useDeptHealth = create<DeptHealthState>((set) => ({
  healths: {},
  loaded: false,
  loading: false,
  error: null,
  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const list = await fetchDeptHealth();
      const map: Record<string, DepartmentHealth> = {};
      for (const h of list) map[h.department_id] = h;
      set({ healths: map, loaded: true, loading: false, error: null });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  },
}));

/**
 * Convenience hook: invalidate and refetch dept-health after a connector
 * mutation (create/validate/delete/approve-spec/etc) succeeds. Keeps
 * mutation handlers concise.
 */
export const refreshDeptHealth = (): Promise<void> =>
  useDeptHealth.getState().refresh();
