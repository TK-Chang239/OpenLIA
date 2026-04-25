import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OnDemandBriefingButton } from "../OnDemandBriefingButton";

const startMock = vi.fn();
const resetMock = vi.fn();
const stateRef = {
  current: {
    status: "idle" as const,
    phase: null,
    sectionTitles: [],
    sections: [],
    toolCalls: [],
    reportId: null as string | null,
    errorMessage: null as string | null,
  } as {
    status: "idle" | "starting" | "writing" | "complete" | "error";
    phase: null;
    sectionTitles: never[];
    sections: never[];
    toolCalls: never[];
    reportId: string | null;
    errorMessage: string | null;
  },
};

vi.mock("../../report/useReportStream", () => ({
  useReportStream: () => ({
    state: stateRef.current,
    start: startMock,
    reset: resetMock,
  }),
}));

beforeEach(() => {
  startMock.mockReset();
  resetMock.mockReset();
  stateRef.current = {
    status: "idle",
    phase: null,
    sectionTitles: [],
    sections: [],
    toolCalls: [],
    reportId: null,
    errorMessage: null,
  };
});

describe("OnDemandBriefingButton", () => {
  it("click starts the report stream with the MB endpoint", () => {
    render(<OnDemandBriefingButton onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    expect(startMock).toHaveBeenCalledWith({
      url: "/api/departments/morning-briefing/report",
      body: {},
    });
  });

  it("fires onSaved on complete + report_id", async () => {
    const onSaved = vi.fn();
    const { rerender } = render(
      <OnDemandBriefingButton onSaved={onSaved} />,
    );
    stateRef.current = {
      ...stateRef.current,
      status: "complete",
      reportId: "rid-1",
    };
    await act(async () => {
      rerender(<OnDemandBriefingButton onSaved={onSaved} />);
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith("rid-1"));
    expect(resetMock).toHaveBeenCalled();
  });

  it("fires onError on error state", async () => {
    const onError = vi.fn();
    const { rerender } = render(
      <OnDemandBriefingButton onSaved={() => {}} onError={onError} />,
    );
    stateRef.current = {
      ...stateRef.current,
      status: "error",
      errorMessage: "boom",
    };
    await act(async () => {
      rerender(
        <OnDemandBriefingButton onSaved={() => {}} onError={onError} />,
      );
    });
    await waitFor(() => expect(onError).toHaveBeenCalledWith("boom"));
  });
});
