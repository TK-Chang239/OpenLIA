import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WatchlistCard } from "../WatchlistCard";

// Use a far-future date so the timing badge always renders regardless of
// the test runner's wall clock.
const baseEntry = {
  id: "1",
  ticker: "AAPL",
  company_name: "Apple Inc.",
  next_earnings_date: "2099-12-31",
  release_timing: "post_market" as const,
};

describe("WatchlistCard", () => {
  it("renders ticker, company, date, timing badge", () => {
    render(<WatchlistCard entry={baseEntry} onRemove={() => {}} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText(/Dec 31/)).toBeInTheDocument();
    expect(screen.getByText(/Post-Market/i)).toBeInTheDocument();
  });

  it("post-market badge uses warning color classes", () => {
    render(<WatchlistCard entry={baseEntry} onRemove={() => {}} />);
    const badge = screen.getByText(/Post-Market/i);
    expect(badge.className).toContain("--color-warning");
  });

  it("pre-market badge uses info color classes", () => {
    render(
      <WatchlistCard
        entry={{ ...baseEntry, release_timing: "pre_market" }}
        onRemove={() => {}}
      />,
    );
    const badge = screen.getByText(/Pre-Market/i);
    expect(badge.className).toContain("--color-info");
  });

  it("renders Date passed state with error border when date is in the past", () => {
    const overdueDate = "2026-04-22";
    const { container } = render(
      <WatchlistCard
        entry={{ ...baseEntry, next_earnings_date: overdueDate }}
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

  it("renders N/A when no earnings date cached", () => {
    render(
      <WatchlistCard
        entry={{ ...baseEntry, next_earnings_date: null, release_timing: null }}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByText(/—|N\/A|Pending/i)).toBeInTheDocument();
  });
});
