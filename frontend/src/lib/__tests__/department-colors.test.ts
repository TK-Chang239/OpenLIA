import { describe, it, expect } from "vitest";
import { departmentBadgeClass, departmentLabel } from "../department-colors";

describe("departmentBadgeClass", () => {
  it("uses blue for equity research and retail sentiment", () => {
    expect(departmentBadgeClass("equity_research")).toMatch(/--color-dept-blue/);
    expect(departmentBadgeClass("retail_sentiment")).toMatch(/--color-dept-blue/);
  });

  it("uses orange for macro research", () => {
    expect(departmentBadgeClass("macro_research")).toMatch(/--color-dept-orange/);
  });

  it("uses purple for secretary", () => {
    expect(departmentBadgeClass("secretary")).toMatch(/--color-dept-purple/);
  });

  it("uses accent yellow for earnings update and morning briefing", () => {
    expect(departmentBadgeClass("earnings_update")).toMatch(
      /--color-dept-accent-bg/,
    );
    expect(departmentBadgeClass("morning_briefing")).toMatch(
      /--color-dept-accent-bg/,
    );
  });

  it("uses error tint for panic thermometer", () => {
    expect(departmentBadgeClass("panic_thermometer")).toMatch(
      /--color-dept-error/,
    );
  });

  it("falls back to neutral surface for unknown slug", () => {
    expect(departmentBadgeClass("unknown_dept")).toMatch(
      /text-\[--color-text-secondary\]/,
    );
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
