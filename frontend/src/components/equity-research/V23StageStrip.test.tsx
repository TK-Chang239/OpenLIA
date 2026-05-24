import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { V23Stage } from "../../api/equity-research-v2-3";

import { V23StageStrip } from "./V23StageStrip";

const ALL: V23Stage[] = [
  "clarify",
  "plan",
  "research",
  "compute",
  "synthesize",
  "write",
  "visualize",
  "verify",
];

describe("V23StageStrip", () => {
  it("renders all eight pipeline stages in order", () => {
    render(<V23StageStrip activeStage={null} completed={new Set()} />);
    for (const slot of ALL) {
      expect(screen.getByTestId(`er-v2-3-stage-${slot}`)).toHaveAttribute(
        "data-state",
        "pending",
      );
    }
  });

  it("marks the active stage and prior completed stages distinctly", () => {
    render(
      <V23StageStrip
        activeStage="research"
        completed={new Set<V23Stage>(["clarify", "plan"])}
      />,
    );
    expect(screen.getByTestId("er-v2-3-stage-clarify")).toHaveAttribute(
      "data-state",
      "complete",
    );
    expect(screen.getByTestId("er-v2-3-stage-plan")).toHaveAttribute(
      "data-state",
      "complete",
    );
    expect(screen.getByTestId("er-v2-3-stage-research")).toHaveAttribute(
      "data-state",
      "active",
    );
    expect(screen.getByTestId("er-v2-3-stage-compute")).toHaveAttribute(
      "data-state",
      "pending",
    );
  });

  it("surfaces a failed stage in the danger state", () => {
    render(
      <V23StageStrip
        activeStage={null}
        completed={new Set<V23Stage>(["clarify", "plan", "research"])}
        failedStage="compute"
      />,
    );
    expect(screen.getByTestId("er-v2-3-stage-compute")).toHaveAttribute(
      "data-state",
      "failed",
    );
  });

  it("allComplete paints every stage as complete", () => {
    render(
      <V23StageStrip
        activeStage={null}
        completed={new Set<V23Stage>(["clarify"])}
        allComplete
      />,
    );
    for (const slot of ALL) {
      expect(screen.getByTestId(`er-v2-3-stage-${slot}`)).toHaveAttribute(
        "data-state",
        "complete",
      );
    }
  });

  it("shows the retry indicator only on the active stage", () => {
    render(
      <V23StageStrip
        activeStage="write"
        completed={new Set<V23Stage>(["clarify", "plan", "research", "compute", "synthesize"])}
        retryCount={1}
      />,
    );
    expect(screen.getByTestId("er-v2-3-stage-write-retry")).toHaveTextContent(
      /retry 1/i,
    );
    expect(screen.queryByTestId("er-v2-3-stage-clarify-retry")).toBeNull();
  });
});
