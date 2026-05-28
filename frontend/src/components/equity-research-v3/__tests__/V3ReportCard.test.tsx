import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import type { V3ReportDetail } from "../../../api/equity-research-v3";
import { V3ReportCard } from "../V3ReportCard";

const BASE_DETAIL: V3ReportDetail = {
  report: {
    report_id: "abc-123",
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
      markdown: "Body of the overview section.",
      version: 1,
    },
    {
      section_id: "thesis",
      section_index: 1,
      title: "Thesis",
      markdown: "Thesis body [^web_1].",
      version: 1,
    },
  ],
  charts: [
    {
      chart_id: "revenue",
      chart_type: "line",
      title: "Revenue",
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
      provenance: { url: "https://example.com" },
    },
  ],
};

describe("V3ReportCard", () => {
  test("renders subject, meta line, and counts", () => {
    render(<V3ReportCard detail={BASE_DETAIL} />);
    expect(screen.getByText("RKLB.US")).toBeInTheDocument();
    const meta = screen.getByTestId("er-v3-report-card-meta");
    expect(meta).toHaveTextContent("2 sections");
    expect(meta).toHaveTextContent("1 chart");
    expect(meta).toHaveTextContent("1 source");
  });

  test("Open report falls back to opening the standalone HTML window when no FileViewerProvider is mounted", () => {
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);
    render(<V3ReportCard detail={BASE_DETAIL} />);
    const open = screen.getByTestId("er-v3-report-card-open") as HTMLButtonElement;
    open.click();
    expect(openSpy).toHaveBeenCalledWith(
      "/api/departments/equity-research/v3/runs/abc-123/html",
      "_blank",
      "noopener,noreferrer",
    );
    openSpy.mockRestore();
  });

  test("Download PDF + Standalone anchors point at the v3 export URLs", () => {
    render(<V3ReportCard detail={BASE_DETAIL} />);
    const pdf = screen.getByTestId("er-v3-report-card-pdf") as HTMLAnchorElement;
    const standalone = screen.getByTestId(
      "er-v3-report-card-standalone",
    ) as HTMLAnchorElement;
    expect(pdf.getAttribute("href")).toContain(
      "/api/departments/equity-research/v3/runs/abc-123/pdf",
    );
    expect(standalone.getAttribute("href")).toContain(
      "/api/departments/equity-research/v3/runs/abc-123/html",
    );
  });

  test('shows the "Ready" status pill by default', () => {
    render(<V3ReportCard detail={BASE_DETAIL} />);
    expect(screen.getByTestId("er-v3-report-card-ready")).toBeInTheDocument();
    expect(
      screen.queryByTestId("er-v3-report-card-revising"),
    ).toBeNull();
  });

  test('shows "Revising" pill when revising=true', () => {
    render(<V3ReportCard detail={BASE_DETAIL} revising />);
    expect(
      screen.getByTestId("er-v3-report-card-revising"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("er-v3-report-card-ready")).toBeNull();
  });

  test("falls back to first-section text when no preview prop is provided", () => {
    render(<V3ReportCard detail={BASE_DETAIL} />);
    expect(
      screen.getByText(/Body of the overview section/),
    ).toBeInTheDocument();
  });
});
