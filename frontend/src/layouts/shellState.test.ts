import { describe, it, expect } from "vitest";
import { crumbsForPath } from "./shellState";

describe("crumbsForPath", () => {
  it("returns Home for the root path", () => {
    expect(crumbsForPath("/")).toEqual(["Home"]);
  });

  it("returns Home + label for a known department root", () => {
    expect(crumbsForPath("/secretary")).toEqual(["Home", "Secretary"]);
  });

  it("returns Home + Settings for /settings", () => {
    expect(crumbsForPath("/settings")).toEqual(["Home", "Settings"]);
  });

  it("returns Home + Settings + Providers for /settings/providers", () => {
    expect(crumbsForPath("/settings/providers")).toEqual([
      "Home",
      "Settings",
      "Providers",
    ]);
  });

  it("returns Home + Settings + Account for /settings/account", () => {
    expect(crumbsForPath("/settings/account")).toEqual([
      "Home",
      "Settings",
      "Account",
    ]);
  });

  it("returns three-segment crumbs for nested macro research drilldown", () => {
    expect(
      crumbsForPath("/macro-research/drilldown/something"),
    ).toEqual(["Home", "Macro Research", "Drilldown"]);
  });

  it("falls back to Home for an unknown top-level path", () => {
    expect(crumbsForPath("/totally-unknown")).toEqual(["Home"]);
  });
});
