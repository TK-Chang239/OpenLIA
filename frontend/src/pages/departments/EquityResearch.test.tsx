import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import EquityResearch from "./EquityResearch";

vi.mock("../../hooks/useErConfig", () => ({
  useErConfig: () => ({
    config: {
      report_mode: "stock_initiation",
      report_length: "normal",
      sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
      custom_sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
    },
    loading: false,
    patch: vi.fn().mockResolvedValue(undefined),
  }),
}));

describe("EquityResearchPage", () => {
  it("renders welcome state heading and chips", () => {
    render(<EquityResearch />);
    const headings = screen.getAllByRole("heading", { name: /equity research/i });
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "AAPL" })).toBeInTheDocument();
  });

  it("Report Settings button opens the modal", () => {
    render(<EquityResearch />);
    fireEvent.click(screen.getByRole("button", { name: /report settings/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("clicking a chip fills the input and focuses it", async () => {
    render(<EquityResearch />);
    fireEvent.click(screen.getByRole("button", { name: "TSLA" }));
    const input = screen.getByRole("textbox");
    await waitFor(() => expect(input).toHaveValue("TSLA"));
  });
});
