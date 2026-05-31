import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EuScheduleEntry, WatchlistEntry } from "../../../api/earnings-update";
import { WatchlistModal } from "../WatchlistModal";

afterEach(() => { vi.restoreAllMocks(); });

const baseEntry: WatchlistEntry = {
  id: "w1",
  ticker: "AAPL",
  company_name: "Apple Inc.",
  created_at: "2026-01-01T00:00:00Z",
};

function makeScheduleEntry(overrides: Partial<EuScheduleEntry> = {}): EuScheduleEntry {
  return {
    id: "s1",
    ticker: "AAPL",
    fiscal_date: "2099-09-15",
    release_timing: "post_market",
    eps_estimate: null,
    revenue_estimate: null,
    scheduled_run_at: "2099-09-15T23:00:00Z",
    status: "pending",
    attempts: 0,
    report_id: null,
    ...overrides,
  };
}

const defaultProps = {
  open: true,
  entries: [baseEntry],
  onClose: () => {},
  onAdd: async (_ticker: string) => {},
  onRemove: async (_id: string) => {},
};

describe("WatchlistModal", () => {
  it("renders the ticker and company name", () => {
    render(<WatchlistModal {...defaultProps} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
  });

  it("shows fiscal date and timing badge when nextReleaseByTicker has an entry", () => {
    const byTicker = new Map<string, EuScheduleEntry>([
      ["AAPL", makeScheduleEntry()],
    ]);
    render(<WatchlistModal {...defaultProps} nextReleaseByTicker={byTicker} />);
    expect(screen.getByTestId("watchlist-next-date")).toHaveTextContent(/Sep 15/);
    expect(screen.getByTestId("watchlist-timing-badge")).toHaveTextContent(/Post-Market/i);
  });

  it("shows pre-market badge for pre_market timing", () => {
    const byTicker = new Map<string, EuScheduleEntry>([
      ["AAPL", makeScheduleEntry({ release_timing: "pre_market" })],
    ]);
    render(<WatchlistModal {...defaultProps} nextReleaseByTicker={byTicker} />);
    expect(screen.getByTestId("watchlist-timing-badge")).toHaveTextContent(/Pre-Market/i);
  });

  it("shows neutral no-upcoming-date when ticker is absent from nextReleaseByTicker", () => {
    const byTicker = new Map<string, EuScheduleEntry>();
    render(<WatchlistModal {...defaultProps} nextReleaseByTicker={byTicker} />);
    expect(screen.getByTestId("watchlist-next-date")).toHaveTextContent(/No upcoming date/i);
    expect(screen.queryByTestId("watchlist-timing-badge")).not.toBeInTheDocument();
  });

  it("shows neutral no-upcoming-date when nextReleaseByTicker is omitted", () => {
    render(<WatchlistModal {...defaultProps} />);
    expect(screen.getByTestId("watchlist-next-date")).toHaveTextContent(/No upcoming date/i);
    expect(screen.queryByTestId("watchlist-timing-badge")).not.toBeInTheDocument();
  });

  it("does not render when open is false", () => {
    render(<WatchlistModal {...defaultProps} open={false} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
