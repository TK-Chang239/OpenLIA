import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { DevEvent } from "../../../api/devEvents";

// jsdom does not implement Element.scrollTo; DevPanel calls it on events.
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => undefined;
}

const isDevModeEnabledMock = vi.fn();
const streamDevEventsMock = vi.fn();

vi.mock("../../../api/devEvents", () => ({
  isDevModeEnabled: () => isDevModeEnabledMock(),
  streamDevEvents: (cb: (e: DevEvent) => void) => streamDevEventsMock(cb),
}));

import { DevPanel } from "../DevPanel";

function ev(
  seq: number,
  category: string,
  payload: Record<string, unknown>,
): DevEvent {
  return {
    seq,
    ts: "2026-05-15T00:00:00.000Z",
    category,
    message: category,
    payload,
  };
}

describe("DevPanel cost tab", () => {
  beforeEach(() => {
    isDevModeEnabledMock.mockReset();
    streamDevEventsMock.mockReset();
  });

  it("renders cost metrics derived from streamed events", async () => {
    isDevModeEnabledMock.mockResolvedValue(true);

    let emit: ((e: DevEvent) => void) | null = null;
    streamDevEventsMock.mockImplementation((cb: (e: DevEvent) => void) => {
      emit = cb;
      return () => undefined;
    });

    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <DevPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("dev-panel")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(emit).not.toBeNull();
    });

    // Stream a known set of events:
    //  r1 — 1 native invoked + 1 configured tool_call web_search (double-bill candidate)
    //  r2 — 1 rescue (counts as a search; rescue rate contributor)
    const events: DevEvent[] = [
      ev(1, "report.request", { report_id: "r1" }),
      ev(2, "report.web_search.invoked", { report_id: "r1" }),
      ev(3, "report.tool_call", { report_id: "r1", tool_name: "web_search" }),
      ev(4, "report.request", { report_id: "r2" }),
      ev(5, "web_search.rescue", { report_id: "r2" }),
    ];

    act(() => {
      for (const e of events) emit!(e);
    });

    // Open the panel
    await user.click(screen.getByRole("button", { name: /dev panel/i }));

    // Switch to Cost tab
    await user.click(screen.getByTestId("dev-panel-tab-cost"));

    // Metrics:
    //  reports = 2
    //  searches = 3, searches/report = 1.50
    //  rescue rate = 1/2 = 50.0%
    //  double-bill = 1/2 = 50.0%
    expect(screen.getByTestId("cost-report-count")).toHaveTextContent("2");
    expect(screen.getByTestId("cost-searches-per-report")).toHaveTextContent(
      "1.50",
    );
    expect(screen.getByTestId("cost-rescue-rate")).toHaveTextContent("50.0%");
    expect(screen.getByTestId("cost-double-bill")).toHaveTextContent("50.0%");
  });

  it("shows zeros when no events have streamed", async () => {
    isDevModeEnabledMock.mockResolvedValue(true);
    streamDevEventsMock.mockImplementation(() => () => undefined);

    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <DevPanel />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("dev-panel")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /dev panel/i }));
    await user.click(screen.getByTestId("dev-panel-tab-cost"));

    expect(screen.getByTestId("cost-report-count")).toHaveTextContent("0");
    expect(screen.getByTestId("cost-searches-per-report")).toHaveTextContent(
      "0.00",
    );
    expect(screen.getByTestId("cost-rescue-rate")).toHaveTextContent("0.0%");
    expect(screen.getByTestId("cost-double-bill")).toHaveTextContent("0.0%");
  });
});
