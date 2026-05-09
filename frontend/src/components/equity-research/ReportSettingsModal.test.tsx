import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportSettingsModal } from "./ReportSettingsModal";
import type { ErConfig } from "../../api/equity-research";

const baseConfig: ErConfig = {
  report_mode: "stock_initiation",
  report_length: "normal",
  sections_by_mode: {
    stock_initiation: ["company_overview", "industry_overview"],
    stock_update: ["investment_thesis", "event_analysis"],
    sector_research: ["sector_thesis"],
  },
  custom_sections_by_mode: {
    stock_initiation: [],
    stock_update: [],
    sector_research: [],
  },
};

describe("ReportSettingsModal", () => {
  it("renders sections for the initially selected mode", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    expect(screen.getByText("Company Overview")).toBeInTheDocument();
    expect(screen.getByText("Industry Overview")).toBeInTheDocument();
  });

  it("switching mode replaces the visible section list", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "Stock Update" }));
    expect(
      screen.getByText("Investment Thesis / Key Takeaway"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Company Overview")).not.toBeInTheDocument();
  });

  it("unchecking a section and saving calls onSave with the patched config", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByText("Industry Overview"));
    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const patch = onSave.mock.calls[0][0];
    expect(patch.sections_by_mode.stock_initiation).toEqual(["company_overview"]);
  });

  it("clicking Add custom section reveals the title input", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /add custom section/i }));
    expect(
      screen.getByLabelText("New custom section title"),
    ).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: /add section/i });
    expect(confirm).toBeDisabled();
  });

  it("changing report length toggle updates the patch on save", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "Elaborative" }));
    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].report_length).toBe("elaborative");
  });
});
