import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EuEvent } from "../../../api/earnings-update";
import type { EuStreamState } from "../../../hooks/useEuRunStream";
import { EuGeneratingCard } from "../feed/EuGeneratingCard";

function makeStream(overrides: Partial<EuStreamState> = {}): EuStreamState {
  return {
    status: "streaming",
    events: [],
    sectionsWritten: 0,
    chartsEmitted: 0,
    toolCallsInflight: 0,
    terminalMessage: null,
    errorMessage: null,
    cancel: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

const ev = (type: EuEvent["type"], payload: Record<string, unknown> = {}): EuEvent => ({
  type,
  payload,
});

describe("EuGeneratingCard", () => {
  it("renders the badge, fallback title, elapsed, and four pips", () => {
    render(<EuGeneratingCard ticker="AAPL" stream={makeStream()} />);
    expect(screen.getByText("Generating Update")).toBeTruthy();
    expect(screen.getByText("AAPL — Earnings Update")).toBeTruthy();
    expect(screen.getByText("0:00")).toBeTruthy();
    expect(screen.getByTestId("eu-gen-pips").querySelectorAll("[data-pip]")).toHaveLength(4);
  });

  it("uses the run.started subject as the title when present", () => {
    const stream = makeStream({ events: [ev("run.started", { subject: "Apple Inc. — Q2 FY26" })] });
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    expect(screen.getByText("Apple Inc. — Q2 FY26")).toBeTruthy();
  });

  it("shows the research phase label and mono code from a data tool call", () => {
    const stream = makeStream({
      events: [ev("tool.called", { tool_name: "get_earnings_calendar", args_summary: "AAPL Q2" })],
    });
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    expect(screen.getByText("Reading the release")).toBeTruthy();
    expect(screen.getByText("AAPL Q2")).toBeTruthy();
    expect(screen.getByTestId("eu-gen-pips").querySelector('[data-pip="research"]')?.getAttribute("data-state")).toBe("active");
  });

  it("calls stream.cancel when Cancel is clicked", () => {
    const stream = makeStream();
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(stream.cancel).toHaveBeenCalledTimes(1);
  });

  it("disables Cancel once the run is no longer streaming", () => {
    const stream = makeStream({ status: "completed" });
    render(<EuGeneratingCard ticker="AAPL" stream={stream} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
  });
});
