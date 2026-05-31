import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EuUpNextCard } from "../feed/EuUpNextCard";

describe("EuUpNextCard", () => {
  it("shows ticker, fiscal date, and timing badge", () => {
    render(
      <EuUpNextCard
        entry={{
          id: "s1",
          ticker: "MSFT.US",
          fiscal_date: "2026-06-15",
          release_timing: "post_market",
          eps_estimate: null,
          revenue_estimate: null,
          scheduled_run_at: "2026-06-15T23:00:00Z",
          status: "pending",
          attempts: 0,
          report_id: null,
        }}
      />,
    );
    expect(screen.getByText(/MSFT/)).toBeTruthy();
    expect(screen.getByText(/2026-06-15/)).toBeTruthy();
    expect(screen.getByText(/post/i)).toBeTruthy();
  });
});
