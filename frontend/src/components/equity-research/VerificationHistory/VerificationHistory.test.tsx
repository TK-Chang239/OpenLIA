import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VerificationHistory } from "./VerificationHistory";
import type { VerificationHistoryData } from "./VerificationHistory";

const entry1 = {
  issue: {
    issue_type: "missing_citation",
    section_id: "valuation",
    severity: "blocker" as const,
    evidence: "No source for P/E ratio claim",
    suggested_fix: "Add citation",
    detector: "deterministic" as const,
  },
  raised_at_round: 1,
  final_resolution: "resolved" as const,
  resolved_in_round: 2,
};

const entry2 = {
  issue: {
    issue_type: "stale_data",
    section_id: null,
    severity: "warning" as const,
    evidence: "Price data is 3 days old",
    detector: "llm" as const,
  },
  raised_at_round: 1,
  final_resolution: "persisted_degraded" as const,
};

const baseHistory: VerificationHistoryData = {
  entries: [entry1, entry2],
  total_issues_raised: 2,
  resolved_on_first_retry: 1,
  persisted_to_degraded: 1,
};

describe("VerificationHistory", () => {
  it("returns null when devMode is false", () => {
    const { container } = render(
      <VerificationHistory history={baseHistory} devMode={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders table with entries when devMode is true", () => {
    render(<VerificationHistory history={baseHistory} devMode={true} />);
    expect(screen.getByText("Verification History")).toBeInTheDocument();
    expect(screen.getByText("missing_citation")).toBeInTheDocument();
    expect(screen.getByText("stale_data")).toBeInTheDocument();
  });

  it("applies status-specific row classes per final_resolution", () => {
    const { container } = render(
      <VerificationHistory history={baseHistory} devMode={true} />
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows[0].className).toContain("resolution-resolved");
    expect(rows[1].className).toContain("resolution-persisted_degraded");
  });

  it("shows total issues count", () => {
    render(<VerificationHistory history={baseHistory} devMode={true} />);
    expect(screen.getByText(/2 issues raised/)).toBeInTheDocument();
  });

  it("shows DEV badge", () => {
    render(<VerificationHistory history={baseHistory} devMode={true} />);
    expect(screen.getByText("DEV")).toBeInTheDocument();
  });

  it("renders section id column — dash when null", () => {
    render(<VerificationHistory history={baseHistory} devMode={true} />);
    expect(screen.getByText("valuation")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows singular issue count", () => {
    const singleEntry: VerificationHistoryData = {
      entries: [entry1],
      total_issues_raised: 1,
    };
    render(<VerificationHistory history={singleEntry} devMode={true} />);
    expect(screen.getByText(/1 issue raised/)).toBeInTheDocument();
  });

  it("renders evidence text", () => {
    render(<VerificationHistory history={baseHistory} devMode={true} />);
    expect(screen.getByText("No source for P/E ratio claim")).toBeInTheDocument();
  });
});
