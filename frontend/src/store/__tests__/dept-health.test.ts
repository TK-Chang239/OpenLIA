import { describe, it, expect, vi, beforeEach } from "vitest";
import { useDeptHealth, refreshDeptHealth } from "../dept-health";
import * as api from "../../api/dept-health";

beforeEach(() => {
  vi.restoreAllMocks();
  // Reset store state between tests.
  useDeptHealth.setState({
    healths: {},
    loaded: false,
    loading: false,
    error: null,
  });
});

describe("dept-health store", () => {
  it("refresh populates healths keyed by department_id", async () => {
    vi.spyOn(api, "fetchDeptHealth").mockResolvedValue([
      {
        department_id: "secretary",
        status: "active",
        reason: null,
        missing_categories: [],
        unresolved_needs: [],
      },
      {
        department_id: "macro_research",
        status: "disabled",
        reason: "Missing required categories: financial",
        missing_categories: ["financial"],
        unresolved_needs: [],
      },
    ]);

    await useDeptHealth.getState().refresh();
    const state = useDeptHealth.getState();
    expect(state.loaded).toBe(true);
    expect(state.healths["secretary"].status).toBe("active");
    expect(state.healths["macro_research"].reason).toMatch(/financial/);
  });

  it("captures an error when fetch fails", async () => {
    vi.spyOn(api, "fetchDeptHealth").mockRejectedValue(new Error("boom"));
    await useDeptHealth.getState().refresh();
    const state = useDeptHealth.getState();
    expect(state.error).toBe("boom");
    expect(state.loaded).toBe(false);
  });

  it("refreshDeptHealth() helper invokes refresh()", async () => {
    const spy = vi.spyOn(api, "fetchDeptHealth").mockResolvedValue([]);
    await refreshDeptHealth();
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
