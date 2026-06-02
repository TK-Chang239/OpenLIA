import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import * as settingsApi from "../../api/settings";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import type { EuStreamState } from "../../hooks/useEuRunStream";
import EarningsUpdate from "./EarningsUpdate";

// Mutable stream state the mocked hook returns; tests reassign it and
// rerender to simulate SSE lifecycle transitions.
let streamState: EuStreamState;

vi.mock("../../hooks/useEuRunStream", () => ({
  useEuRunStream: () => streamState,
}));

// Modal stub exposing a button that fires onStarted, so a test can put the
// page into its "live run" state without the real modal/network.
vi.mock("../../components/earnings-update/OnDemandReportModal", () => ({
  OnDemandReportModal: ({
    open,
    onStarted,
  }: {
    open: boolean;
    onStarted: (reportId: string, ticker: string) => void;
  }) =>
    open ? (
      <button data-testid="start-run" onClick={() => onStarted("r1", "AAPL")}>
        start
      </button>
    ) : null,
}));

vi.mock("../../components/earnings-update/calendar/EuCalendar", () => ({
  EuCalendar: () => <div data-testid="eu-cal-month" />,
}));

const cancelFn = vi.fn().mockResolvedValue(undefined);

function makeStream(status: EuStreamState["status"]): EuStreamState {
  return {
    status,
    events: [],
    sectionsWritten: 0,
    chartsEmitted: 0,
    toolCallsInflight: 0,
    terminalMessage: null,
    errorMessage: null,
    cancel: cancelFn,
  };
}

const baseSettings: api.EuSettings = {
  provider_kind: "anthropic",
  model: "claude-sonnet-4-6",
  template_id: "eu_default",
  language: "en",
  length: "normal",
  reasoning_effort: null,
  enabled_provider_ids: ["eodhd"],
  web_search_enabled: false,
  instructions_id: null,
  batch_enabled: false,
};

function renderPage() {
  return render(
    <FileViewerProvider>
      <EarningsUpdate />
    </FileViewerProvider>,
  );
}

describe("EarningsUpdate live run lifecycle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    streamState = makeStream("streaming");
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "fetchRuns").mockResolvedValue([]);
    vi.spyOn(api, "fetchSettings").mockResolvedValue(baseSettings);
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({ schedule: [] });
    vi.spyOn(api, "fetchTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  async function startLiveRun() {
    fireEvent.click(
      await screen.findByRole("button", { name: /generate report/i }),
    );
    fireEvent.click(screen.getByTestId("start-run"));
    return screen.findByTestId("eu-generating-card");
  }

  it("shows the generating card while a run streams and Cancel calls stream.cancel", async () => {
    renderPage();
    await startLiveRun();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(cancelFn).toHaveBeenCalledTimes(1);
  });

  it("dismisses the live generating card once the run is cancelled", async () => {
    const { rerender } = renderPage();
    await startLiveRun();

    // Server emits run.cancelled -> hook surfaces a terminal "cancelled".
    streamState = makeStream("cancelled");
    rerender(
      <FileViewerProvider>
        <EarningsUpdate />
      </FileViewerProvider>,
    );

    await waitFor(() =>
      expect(screen.queryByTestId("eu-generating-card")).not.toBeInTheDocument(),
    );
  });

  it("dismisses the live generating card when the run fails", async () => {
    const { rerender } = renderPage();
    await startLiveRun();

    streamState = makeStream("failed");
    rerender(
      <FileViewerProvider>
        <EarningsUpdate />
      </FileViewerProvider>,
    );

    await waitFor(() =>
      expect(screen.queryByTestId("eu-generating-card")).not.toBeInTheDocument(),
    );
  });

  it("deletes the completed live card and clears it from the feed", async () => {
    const del = vi.spyOn(api, "deleteRun").mockResolvedValue(undefined);
    const { rerender } = renderPage();
    await startLiveRun();

    // The run finishes — the live block swaps the generating card for the
    // completed EuBigCard, which carries a delete control.
    streamState = makeStream("completed");
    rerender(
      <FileViewerProvider>
        <EarningsUpdate />
      </FileViewerProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: /remove report/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

    // Deletes the live run id and clears the card (setLive(null)).
    await waitFor(() => expect(del).toHaveBeenCalledWith("r1"));
    await waitFor(() =>
      expect(screen.queryByTestId("eu-big-card")).not.toBeInTheDocument(),
    );
  });
});
