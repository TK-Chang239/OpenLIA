import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { CalendarEvent } from "../calendarHelpers";
import { EuCalendarDayPopover } from "../EuCalendarDayPopover";

const reported: CalendarEvent = {
  ticker: "MSFT",
  status: "reported",
  session: "tbd",
  dateKey: "2026-04-29",
  reportId: "r1",
  epsEstimate: null,
  revenueEstimate: null,
  subject: "MSFT Q3 FY26 earnings",
};

const scheduled: CalendarEvent = {
  ticker: "AAPL",
  status: "scheduled",
  session: "am",
  dateKey: "2026-04-30",
  reportId: null,
  epsEstimate: "1.50",
  revenueEstimate: "94.2B",
  subject: null,
};

describe("EuCalendarDayPopover", () => {
  it("renders nothing when dateKey is null", () => {
    const { container } = render(
      <EuCalendarDayPopover dateKey={null} events={[]} onClose={() => {}} onOpenReport={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the day's events and the report count", () => {
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-30"
        events={[reported, scheduled]}
        onClose={() => {}}
        onOpenReport={() => {}}
      />,
    );
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/2 reports/i)).toBeInTheDocument();
    expect(screen.getByText(/94.2B/)).toBeInTheDocument();
  });

  it("opens a report when a reported event is clicked", () => {
    const onOpenReport = vi.fn();
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-29"
        events={[reported]}
        onClose={() => {}}
        onOpenReport={onOpenReport}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /MSFT/ }));
    expect(onOpenReport).toHaveBeenCalledWith("r1");
  });

  it("calls onClose from the close button", () => {
    const onClose = vi.fn();
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-30"
        events={[scheduled]}
        onClose={onClose}
        onOpenReport={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-30"
        events={[scheduled]}
        onClose={onClose}
        onOpenReport={() => {}}
      />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("closes when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-30"
        events={[scheduled]}
        onClose={onClose}
        onOpenReport={() => {}}
      />,
    );
    // The backdrop is the aria-hidden overlay rendered just before the dialog.
    const backdrop = screen.getByRole("dialog").previousSibling as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });
});
