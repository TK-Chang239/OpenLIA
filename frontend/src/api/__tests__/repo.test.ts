import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../client";
import { saveMbRunToRepo, unsaveMbRunFromRepo, listSavedMbRuns } from "../repo";

afterEach(() => { vi.restoreAllMocks(); });

function mockJson(value: unknown) {
  return vi.spyOn(client, "fetchJson").mockResolvedValue(value as never);
}

describe("MB repo helpers", () => {
  it("saveMbRunToRepo POSTs the mb_v2_report_id", async () => {
    const spy = mockJson({ id: "x", report_id: "mb-1", created_at: "" });
    await saveMbRunToRepo("mb-1");
    expect(spy).toHaveBeenCalledWith("/api/repo/mb-runs", {
      method: "POST",
      json: { mb_v2_report_id: "mb-1" },
    });
  });

  it("unsaveMbRunFromRepo DELETEs with the query param", async () => {
    const spy = mockJson(null);
    await unsaveMbRunFromRepo("mb-1");
    expect(spy).toHaveBeenCalledWith(
      "/api/repo/mb-runs?mb_v2_report_id=mb-1",
      { method: "DELETE" },
    );
  });

  it("listSavedMbRuns GETs the mb-runs surface", async () => {
    const spy = mockJson({ saved_report_ids: ["mb-1"] });
    const res = await listSavedMbRuns();
    expect(spy).toHaveBeenCalledWith("/api/repo/mb-runs");
    expect(res.saved_report_ids).toEqual(["mb-1"]);
  });
});
