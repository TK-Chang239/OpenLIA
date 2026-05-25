import { describe, expect, it } from "vitest";

import { v23ReportTypeToPillMode } from "./v23-pill-mode";

describe("v23ReportTypeToPillMode — pill label matches v2.3 selection", () => {
  it("maps initiation -> stock_initiation", () => {
    expect(v23ReportTypeToPillMode("initiation")).toBe("stock_initiation");
  });

  it("maps update -> stock_update", () => {
    expect(v23ReportTypeToPillMode("update")).toBe("stock_update");
  });

  it("maps sector_research -> sector_research (passthrough)", () => {
    expect(v23ReportTypeToPillMode("sector_research")).toBe("sector_research");
  });
});
