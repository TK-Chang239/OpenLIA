import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import type { V3ReportDetail } from "../../../api/equity-research-v3";
import type { V3Event } from "../../../api/equity-research-v3";
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

  test("Standalone anchor still points at the v3 HTML endpoint", () => {
    render(<V3ReportCard detail={BASE_DETAIL} />);
    const standalone = screen.getByTestId(
      "er-v3-report-card-standalone",
    ) as HTMLAnchorElement;
    expect(standalone.getAttribute("href")).toContain(
      "/api/departments/equity-research/v3/runs/abc-123/html",
    );
  });

  test("Download + Save-to-repo buttons render alongside Open report", () => {
    render(<V3ReportCard detail={BASE_DETAIL} />);
    // Consolidated dropdown — the inline PDF/Word buttons collapse
    // into a single ReportDownloadButton with format options.
    expect(
      screen.getByTestId("er-v3-report-card-download"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("er-v3-report-card-save"),
    ).toBeInTheDocument();
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

const LIVE = {
  status: "streaming" as const,
  sectionsWritten: 3,
  chartsEmitted: 1,
  citationsSeen: 4,
  elapsedSeconds: 22.4,
  events: [
    { type: "section.written", payload: { section_id: "overview", char_count: 1500 } },
  ] as V3Event[],
  terminalMessage: null,
  errorMessage: null,
};

describe("V3ReportCard — generating phase", () => {
  test("shows a GENERATING pill, the subject, and live counts", () => {
    render(
      <V3ReportCard
        phase="generating"
        subject="AAPL"
        templateLabel="Stock Initiation"
        createdAtIso={null}
        live={LIVE}
      />,
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("er-v3-report-card-generating")).toBeInTheDocument();
    const meta = screen.getByTestId("er-v3-report-card-meta");
    expect(meta).toHaveTextContent("3 sections");
    expect(meta).toHaveTextContent("4 sources");
    expect(meta).toHaveTextContent("Elapsed 22.4s");
  });

  test("renders the activity feed and hides the action row while generating", () => {
    render(
      <V3ReportCard
        phase="generating"
        subject="AAPL"
        templateLabel="Stock Initiation"
        createdAtIso={null}
        live={LIVE}
      />,
    );
    expect(screen.getByTestId("er-v3-activity-feed")).toBeInTheDocument();
    expect(screen.queryByTestId("er-v3-report-card-open")).toBeNull();
  });

  test("shows a FAILED pill and the error message when the stream fails before detail", () => {
    render(
      <V3ReportCard
        phase="generating"
        subject="AAPL"
        templateLabel="Stock Initiation"
        createdAtIso={null}
        live={{ ...LIVE, status: "failed", errorMessage: "stream dropped" }}
      />,
    );
    expect(screen.getByTestId("er-v3-report-card-failed")).toBeInTheDocument();
    expect(screen.getByText("stream dropped")).toBeInTheDocument();
  });

  test("ready phase shows Generated-in time from generatedSeconds", () => {
    render(<V3ReportCard detail={BASE_DETAIL} generatedSeconds={22.4} />);
    expect(screen.getByTestId("er-v3-report-card-meta")).toHaveTextContent(
      "Generated in 22.4s",
    );
  });
});
