import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { V23RunPayload } from "../../api/equity-research-v2-3";

import { V23ReportCard } from "./V23ReportCard";

const PAYLOAD: V23RunPayload = {
  run_id: "run-abc123",
  tickers: ["NVDA", "AVGO"],
  report_type: "initiation",
  language: "en",
  thesis: {
    language: "en",
    central_argument:
      "Memory pricing is the dominant constraint on AI infra margins through 2026.",
    key_takeaways: ["First takeaway", "Second takeaway"],
    valuation_stance: "Base $1,420 (12% upside)",
    canonical_figures: [{ fact_id: "fig.dcf_base", display: "DCF $1,420" }],
  },
  sections: [
    { id: "overview", title: "Company Overview" },
    { id: "valuation", title: "Valuation" },
  ],
  section_bodies: {
    overview: "Body.",
    valuation: "Body.",
  },
  footnotes: ["EODHD FY25 10-K", "Bloomberg consensus", "Press release"],
  charts: [
    {
      id: "fig_rev",
      section_id: "overview",
      claim: "rev",
      chart_type: "column",
      title: "Revenue",
      category_labels: [],
      series: [],
      x_axis_label: null,
      y_axis_label: null,
    },
  ],
  figure_labels: { fig_rev: 1 },
  bundle_facts: {},
};

describe("V23ReportCard", () => {
  it("renders report type, tickers and the first sentence of the thesis", () => {
    render(
      <V23ReportCard payload={PAYLOAD} completedAt={null} onOpen={() => {}} />,
    );
    expect(screen.getByText(/Stock Initiation Report/i)).toBeInTheDocument();
    expect(screen.getByText(/NVDA, AVGO/)).toBeInTheDocument();
    expect(
      screen.getByText(/Memory pricing is the dominant constraint/),
    ).toBeInTheDocument();
  });

  it("counts charts and footnotes with correct pluralisation", () => {
    render(
      <V23ReportCard payload={PAYLOAD} completedAt={null} onOpen={() => {}} />,
    );
    expect(screen.getByText(/1 chart\b/)).toBeInTheDocument();
    expect(screen.getByText(/3 footnotes/)).toBeInTheDocument();
  });

  it("fires onOpen when the user clicks Open Report", () => {
    const onOpen = vi.fn();
    render(
      <V23ReportCard payload={PAYLOAD} completedAt={null} onOpen={onOpen} />,
    );
    fireEvent.click(screen.getByTestId("er-v2-3-report-card-open"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("exposes a docx download link pointing at the run", () => {
    render(
      <V23ReportCard payload={PAYLOAD} completedAt={null} onOpen={() => {}} />,
    );
    const link = screen.getByTestId(
      "er-v2-3-report-card-download",
    ) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toContain("/runs/run-abc123/docx");
  });
});
