import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CapabilitySidebar } from "./CapabilitySidebar";
import type { CapabilityManifest } from "../../../api/capabilities";

const baseManifest: CapabilityManifest = {
  engine_version: "2.2",
  dev_mode: false,
  supported: [
    { id: "dcf_valuation", summary: "DCF valuation model" },
  ],
  unsupported: [
    {
      id: "scenario_analysis",
      summary: "Multi-scenario analysis",
      planned_in: "2.3",
      user_message: "Scenario analysis is not yet available.",
    },
  ],
};

describe("CapabilitySidebar", () => {
  it("renders supported and unsupported capability lists", () => {
    render(<CapabilitySidebar manifest={baseManifest} />);
    expect(screen.getByText("Supported")).toBeInTheDocument();
    expect(screen.getByText("Not yet supported")).toBeInTheDocument();
    expect(screen.getByText("DCF valuation model")).toBeInTheDocument();
    expect(
      screen.getByText("Scenario analysis is not yet available.")
    ).toBeInTheDocument();
  });

  it("displays engine version", () => {
    render(<CapabilitySidebar manifest={baseManifest} />);
    expect(screen.getByText("Engine v2.2")).toBeInTheDocument();
  });

  it("displays planned_in version for unsupported", () => {
    render(<CapabilitySidebar manifest={baseManifest} />);
    expect(screen.getByText("planned for v2.3")).toBeInTheDocument();
  });

  it("omits planned_in when null", () => {
    const manifest: CapabilityManifest = {
      ...baseManifest,
      unsupported: [
        {
          id: "scenario_analysis",
          summary: "Multi-scenario analysis",
          planned_in: null,
          user_message: "Scenario analysis is not yet available.",
        },
      ],
    };
    render(<CapabilitySidebar manifest={manifest} />);
    expect(screen.queryByText(/planned for/)).toBeNull();
  });
});
