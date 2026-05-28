import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import * as api from "../../../../api/equity-research-v3";
import { V3ReportRenderer } from "../V3ReportRenderer";

vi.mock("../../../../api/equity-research-v3", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    getV3Run: vi.fn(),
  };
});

const DETAIL: api.V3ReportDetail = {
  report: {
    report_id: "rpt-1",
    subject: "RKLB.US",
    template_id: "initiation_default",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-05-27T10:00:00Z",
    completed_at: "2026-05-27T10:05:00Z",
  },
  error_message: null,
  sections: [
    {
      section_id: "overview",
      section_index: 0,
      title: "Overview",
      markdown: "Rocket Lab is a launch provider [^web_1].",
      version: 1,
    },
    {
      section_id: "risks",
      section_index: 1,
      title: "Risks",
      markdown: "## Counterparty risk\n\nFew customers carry the book.",
      version: 2,
    },
  ],
  charts: [
    {
      chart_id: "rev_trend",
      chart_type: "line",
      title: "Revenue trend",
      spec: {},
      rendered_url: null,
      version: 1,
    },
  ],
  citations: [
    {
      source_id: "web_1",
      tool_name: "web_search",
      display_index: 1,
      provenance: { url: "https://example.com/rklb" },
    },
  ],
};

beforeEach(() => {
  vi.mocked(api.getV3Run).mockResolvedValue(DETAIL);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("V3ReportRenderer", () => {
  test("fetches and renders report header + sections + bibliography", async () => {
    render(
      <V3ReportRenderer source={{ kind: "v3_report", reportId: "rpt-1" }} />,
    );
    await waitFor(() => {
      expect(api.getV3Run).toHaveBeenCalledWith("rpt-1");
      expect(screen.getByText("RKLB.US")).toBeInTheDocument();
    });
    expect(screen.getByTestId("v3-report-section-overview")).toBeInTheDocument();
    expect(screen.getByTestId("v3-report-section-risks")).toBeInTheDocument();
    expect(
      screen.getByTestId("v3-report-section-revised-risks"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("v3-report-bibliography")).toBeInTheDocument();
  });

  test("rewrites [^source_id] markers to numeric display indices", async () => {
    render(
      <V3ReportRenderer source={{ kind: "v3_report", reportId: "rpt-1" }} />,
    );
    await waitFor(() => {
      expect(api.getV3Run).toHaveBeenCalled();
    });
    // The "Rocket Lab is a launch provider [^web_1]." section's
    // marker should now render as [^1] (web_1 → display_index 1).
    const overview = screen.getByTestId("v3-report-section-overview");
    expect(overview.textContent).toMatch(/\[\^1\]/);
    expect(overview.textContent).not.toMatch(/\[\^web_1\]/);
  });

  test("bibliography links to citation URLs when provenance carries one", async () => {
    render(
      <V3ReportRenderer source={{ kind: "v3_report", reportId: "rpt-1" }} />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("v3-report-bibliography")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: "https://example.com/rklb" });
    expect(link.getAttribute("href")).toBe("https://example.com/rklb");
    expect(link.getAttribute("target")).toBe("_blank");
  });

  test("surfaces a retryable error when the fetch fails", async () => {
    vi.mocked(api.getV3Run).mockRejectedValue(new Error("nope"));
    render(
      <V3ReportRenderer source={{ kind: "v3_report", reportId: "rpt-1" }} />,
    );
    await waitFor(() => {
      expect(screen.getByText(/nope/)).toBeInTheDocument();
    });
  });
});
