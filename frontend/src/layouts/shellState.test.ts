import { describe, it, expect } from "vitest";
import { crumbsForPath } from "./shellState";

describe("crumbsForPath", () => {
  it("returns Home for the root path", () => {
    expect(crumbsForPath("/")).toEqual(["nav.home"]);
  });

  it("returns Home + label for a known department root", () => {
    expect(crumbsForPath("/secretary")).toEqual(["nav.home", "nav.secretary"]);
  });

  it("returns Home + Settings for /settings", () => {
    expect(crumbsForPath("/settings")).toEqual(["nav.home", "nav.settings"]);
  });

  it("returns Home + Settings + Providers for /settings/providers", () => {
    expect(crumbsForPath("/settings/providers")).toEqual([
      "nav.home",
      "nav.settings",
      "Providers",
    ]);
  });

  it("returns Home + Settings + Account for /settings/account", () => {
    expect(crumbsForPath("/settings/account")).toEqual([
      "nav.home",
      "nav.settings",
      "Account",
    ]);
  });

  it("returns three-segment crumbs for nested macro research drilldown", () => {
    expect(
      crumbsForPath("/macro-research/drilldown/something"),
    ).toEqual(["nav.home", "nav.macro_research", "Drilldown"]);
  });

  it("falls back to Home for an unknown top-level path", () => {
    expect(crumbsForPath("/totally-unknown")).toEqual(["nav.home"]);
  });

  it("maps /equity-research-v3 to the Equity Research crumb", () => {
    expect(crumbsForPath("/equity-research-v3")).toEqual([
      "nav.home",
      "nav.equity_research",
    ]);
  });
});
