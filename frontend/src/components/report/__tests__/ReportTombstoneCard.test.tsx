import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { ReportTombstoneCard } from "../ReportTombstoneCard";
import { StructuredReportRenderer } from "../../viewer/renderers/StructuredReportRenderer";

describe("ReportTombstoneCard", () => {
  it("renders the retention heading and message", () => {
    render(<ReportTombstoneCard expiredAt={null} />);
    expect(
      screen.getByText(/no longer available/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/removed under the data-retention policy/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("report-tombstone-card")).toBeInTheDocument();
  });

  it("shows the removed-on date when expiredAt is present", () => {
    render(<ReportTombstoneCard expiredAt="2026-08-01T00:00:00Z" />);
    expect(screen.getByText(/removed on/i)).toBeInTheDocument();
  });

  it("omits the removed-on line when expiredAt is absent", () => {
    render(<ReportTombstoneCard expiredAt={null} />);
    expect(screen.queryByText(/removed on/i)).toBeNull();
  });
});

describe("StructuredReportRenderer — tombstoned report", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the tombstone card (not RendererError) for an expired report", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.startsWith("/api/reports/")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ schema: null, expired_at: "2026-08-01T00:00:00Z" }),
          } as Response;
        }
        // /api/capabilities probe fired on mount.
        return {
          ok: true,
          status: 200,
          json: async () => ({
            engine_version: "v3",
            dev_mode: false,
            supported: [],
            unsupported: [],
          }),
        } as Response;
      }),
    );

    render(
      <StructuredReportRenderer source={{ kind: "report", reportId: "r1" }} />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("report-tombstone-card")).toBeInTheDocument(),
    );
    // The designed empty-state replaces the raw error path.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/try again/i)).toBeNull();
    expect(screen.getByText(/no longer available/i)).toBeInTheDocument();
  });
});
