import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EuScheduleEntry } from "../../../api/earnings-update";
import { WatchlistCard } from "../WatchlistCard";

const baseEntry = {
  id: "1",
  ticker: "AAPL",
  company_name: "Apple Inc.",
  created_at: "2026-01-01T00:00:00Z",
};

// Use a far-future fiscal date so the timing badge always renders
// regardless of the test runner's wall clock.
function release(
  overrides: Partial<EuScheduleEntry> = {},
): EuScheduleEntry {
  return {
    id: "s1",
    ticker: "AAPL",
    fiscal_date: "2099-12-31",
    release_timing: "post_market",
    eps_estimate: null,
    revenue_estimate: null,
    scheduled_run_at: "2099-12-31T23:00:00Z",
    status: "pending",
    attempts: 0,
    report_id: null,
    ...overrides,
  };
}

describe("WatchlistCard", () => {
  it("renders ticker, company, date, timing badge from nextRelease", () => {
    render(
      <WatchlistCard
        entry={baseEntry}
        nextRelease={release()}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText(/Dec 31/)).toBeInTheDocument();
    expect(screen.getByText(/Post-Market/i)).toBeInTheDocument();
  });

  it("post-market badge uses warning color classes", () => {
    render(
      <WatchlistCard
        entry={baseEntry}
        nextRelease={release()}
        onRemove={() => {}}
      />,
    );
    const badge = screen.getByText(/Post-Market/i);
    expect(badge.className).toContain("--color-warning");
  });

  it("pre-market badge uses info color classes", () => {
    render(
      <WatchlistCard
        entry={baseEntry}
        nextRelease={release({ release_timing: "pre_market" })}
        onRemove={() => {}}
      />,
    );
    const badge = screen.getByText(/Pre-Market/i);
    expect(badge.className).toContain("--color-info");
  });

  it("renders Date passed state with error border when date is in the past", () => {
    const { container } = render(
      <WatchlistCard
        entry={baseEntry}
        nextRelease={release({ fiscal_date: "2026-04-22" })}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByText(/Date passed/i)).toBeInTheDocument();
    const card = container.querySelector('[role="group"]');
    expect(card?.className).toContain("--color-feedback-error");
  });

  it("calls onRemove when × is clicked", () => {
    const onRemove = vi.fn();
    render(<WatchlistCard entry={baseEntry} onRemove={onRemove} />);
    fireEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledWith("1");
  });

  it("shows the neutral no-upcoming-date label when no nextRelease", () => {
    render(<WatchlistCard entry={baseEntry} onRemove={() => {}} />);
    expect(screen.getByText(/No upcoming date/i)).toBeInTheDocument();
  });
});
