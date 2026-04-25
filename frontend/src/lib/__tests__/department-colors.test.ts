import { describe, it, expect } from "vitest";
import { departmentBadgeClass, departmentLabel } from "../department-colors";

describe("departmentBadgeClass", () => {
  it("returns the spec'd tint for each known department", () => {
    expect(departmentBadgeClass("equity_research")).toBe(
      "bg-[--color-info]/10 text-[--color-info]",
    );
    expect(departmentBadgeClass("earnings_update")).toBe(
      "bg-[--color-success]/10 text-[--color-success]",
    );
    expect(departmentBadgeClass("morning_briefing")).toBe(
      "bg-[--color-accent-subtle] text-[--color-accent-primary]",
    );
    expect(departmentBadgeClass("retail_sentiment")).toBe(
      "bg-[--color-info]/10 text-[--color-info]",
    );
    expect(departmentBadgeClass("secretary")).toBe(
      "bg-[--color-surface-hover] text-[--color-text-secondary]",
    );
    expect(departmentBadgeClass("macro_research")).toBe(
      "bg-[--color-warning]/10 text-[--color-warning]",
    );
  });

  it("falls back to neutral surface for unknown slug", () => {
    expect(departmentBadgeClass("unknown_dept")).toMatch(/text-\[--color-text-secondary\]/);
  });
});

describe("departmentLabel", () => {
  it("returns friendly label for known slug", () => {
    expect(departmentLabel("equity_research")).toBe("Equity Research");
    expect(departmentLabel("morning_briefing")).toBe("Morning Briefing");
  });

  it("returns slug as fallback for unknown", () => {
    expect(departmentLabel("foo_bar")).toBe("foo_bar");
  });
});
