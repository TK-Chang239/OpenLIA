import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RecentReport } from "../../../api/morning-briefing";
import { MBArchiveView } from "../MBArchiveView";

describe("MBArchiveView", () => {
  it("empty state shows Sun icon and Go to Settings CTA", () => {
    const onGoToSettings = vi.fn();
    render(
      <MBArchiveView
        reports={[]}
        loading={false}
        onOpen={() => {}}
        onGoToSettings={onGoToSettings}
      />,
    );
    expect(screen.getByTestId("mb-empty-sun")).toBeInTheDocument();
    expect(screen.getByText(/No reports yet/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-empty-go-to-settings"));
    expect(onGoToSettings).toHaveBeenCalled();
  });

  it("groups reports by date heading (Today / Yesterday / older)", () => {
    const today = new Date("2026-04-09T15:00:00Z");
    const yesterday = new Date(today.getTime() - 24 * 3600 * 1000);
    const older = new Date("2026-04-07T12:00:00Z");
    const reports: RecentReport[] = [
      {
        id: "1",
        title: "A",
        report_type: "morning_briefing",
        created_at: today.toISOString(),
      },
      {
        id: "2",
        title: "B",
        report_type: "morning_briefing",
        created_at: yesterday.toISOString(),
      },
      {
        id: "3",
        title: "C",
        report_type: "morning_briefing",
        created_at: older.toISOString(),
      },
    ];
    vi.useFakeTimers();
    vi.setSystemTime(today);
    render(
      <MBArchiveView
        reports={reports}
        loading={false}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText(/^Today —/)).toBeInTheDocument();
    expect(screen.getByText(/^Yesterday —/)).toBeInTheDocument();
    expect(screen.getByText(/^April 7$/)).toBeInTheDocument();
    vi.useRealTimers();
  });
});
