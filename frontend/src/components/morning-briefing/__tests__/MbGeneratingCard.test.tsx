import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MbEvent } from "../../../api/morning-briefing";
import type { MbStreamState } from "../../../hooks/useMbRunStream";
import { MbGeneratingCard } from "../feed/MbGeneratingCard";

function makeStream(overrides: Partial<MbStreamState> = {}): MbStreamState {
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

const ev = (
  type: MbEvent["type"],
  payload: Record<string, unknown> = {},
): MbEvent => ({ type, payload });

describe("MbGeneratingCard", () => {
  it("renders the badge, fallback title, elapsed, and four pips", () => {
    render(<MbGeneratingCard stream={makeStream()} />);
    expect(screen.getByText("Generating Briefing")).toBeTruthy();
    expect(screen.getByText("Morning Briefing")).toBeTruthy();
    expect(screen.getByText("0:00")).toBeTruthy();
    expect(
      screen.getByTestId("mb-gen-pips").querySelectorAll("[data-pip]"),
    ).toHaveLength(4);
  });

  it("uses the run.started subject as the title when present", () => {
    const stream = makeStream({
      events: [ev("run.started", { subject: "Pre-Market Briefing — Jun 2" })],
    });
    render(<MbGeneratingCard stream={stream} />);
    expect(screen.getByText("Pre-Market Briefing — Jun 2")).toBeTruthy();
  });

  it("shows the research phase from a data tool call", () => {
    const stream = makeStream({
      events: [
        ev("tool.called", {
          tool_name: "web_search",
          args_summary: "rate cut",
        }),
      ],
    });
    render(<MbGeneratingCard stream={stream} />);
    expect(screen.getByText("Gathering the news")).toBeTruthy();
    expect(screen.getByText("rate cut")).toBeTruthy();
    expect(
      screen
        .getByTestId("mb-gen-pips")
        .querySelector('[data-pip="research"]')
        ?.getAttribute("data-state"),
    ).toBe("active");
  });

  it("calls stream.cancel when Cancel is clicked", () => {
    const stream = makeStream();
    render(<MbGeneratingCard stream={stream} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(stream.cancel).toHaveBeenCalledTimes(1);
  });

  it("disables Cancel once the run is no longer streaming", () => {
    const stream = makeStream({ status: "completed" });
    render(<MbGeneratingCard stream={stream} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
  });
});
