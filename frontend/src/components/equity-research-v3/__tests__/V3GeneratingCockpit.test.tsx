import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { V3Event } from "../../../api/equity-research-v3";
import { V3GeneratingCockpit } from "../V3GeneratingCockpit";
import type { V3CardLive } from "../V3ReportCard";

function live(overrides: Partial<V3CardLive>): V3CardLive {
  return {
    status: "streaming",
    sectionsWritten: 0,
    chartsEmitted: 0,
    citationsSeen: 0,
    elapsedSeconds: 1,
    events: [],
    terminalMessage: null,
    errorMessage: null,
    ...overrides,
  };
}

describe("V3GeneratingCockpit", () => {
  it("names the current phase from the latest event and shows the sweep", () => {
    const events: V3Event[] = [
      { type: "run.started", payload: { subject: "AAPL", model: "gpt-5" } },
      { type: "tool.called", payload: { turn: 2, tool_name: "get_financials" } },
    ];
    render(<V3GeneratingCockpit live={live({ events })} />);

    expect(screen.getByText("Researching")).toBeInTheDocument();
    // snake_case tool name is humanized for display.
    expect(screen.getByText("get financials")).toBeInTheDocument();
    expect(screen.getByTestId("er-v3-cockpit-sweep")).toBeInTheDocument();
  });

  it("switches to an assembling/finalizing phase and drops the sweep when completed", () => {
    render(<V3GeneratingCockpit live={live({ status: "completed" })} />);

    expect(screen.getByText("Assembling report")).toBeInTheDocument();
    expect(screen.getByText("Finalizing")).toBeInTheDocument();
    expect(screen.queryByTestId("er-v3-cockpit-sweep")).toBeNull();
  });
});
