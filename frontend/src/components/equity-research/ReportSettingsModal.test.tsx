import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportSettingsModal } from "./ReportSettingsModal";
import type { ErConfig } from "../../api/equity-research";

vi.mock("../../auth/useCurrentUser", () => ({
  useCurrentUser: () => ({
    id: "u1",
    email: "u1@example.com",
    display_name: "u1",
    role: "user" as const,
    must_change_password: false,
  }),
}));

vi.mock("../../api/equity-research", async () => {
  const actual = await vi.importActual<typeof import("../../api/equity-research")>(
    "../../api/equity-research",
  );
  return {
    ...actual,
    listErTemplates: vi.fn().mockResolvedValue([]),
    uploadErTemplate: vi.fn(),
    patchErTemplate: vi.fn(),
    deleteErTemplate: vi.fn(),
    fetchErTemplateExtractedText: vi.fn(),
  };
});

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
  selected_template_id_by_mode: {
    stock_initiation: "default",
    stock_update: "default",
    sector_research: "default",
  },
  web_search_budgets_by_mode: {},
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

  it("renders empty budget inputs with framework defaults as placeholders", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    const init = screen.getByLabelText(
      "Web search budget for Stock Initiation",
    ) as HTMLInputElement;
    expect(init.value).toBe("");
    expect(init.placeholder).toBe("10");
    const update = screen.getByLabelText(
      "Web search budget for Stock Update",
    ) as HTMLInputElement;
    expect(update.placeholder).toBe("5");
    const sector = screen.getByLabelText(
      "Web search budget for Sector Research",
    ) as HTMLInputElement;
    expect(sector.placeholder).toBe("15");
  });

  it("pre-fills budget inputs from existing overrides", () => {
    const cfg: ErConfig = {
      ...baseConfig,
      web_search_budgets_by_mode: { stock_initiation: 12, stock_update: 3 },
    };
    render(
      <ReportSettingsModal
        open
        config={cfg}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    expect(
      (screen.getByLabelText(
        "Web search budget for Stock Initiation",
      ) as HTMLInputElement).value,
    ).toBe("12");
    expect(
      (screen.getByLabelText(
        "Web search budget for Stock Update",
      ) as HTMLInputElement).value,
    ).toBe("3");
    // Sector Research: no override → empty.
    expect(
      (screen.getByLabelText(
        "Web search budget for Sector Research",
      ) as HTMLInputElement).value,
    ).toBe("");
  });

  it("entering a budget and saving sends it in the patch (positive ints only, empties dropped)", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />,
    );
    fireEvent.change(
      screen.getByLabelText("Web search budget for Stock Initiation"),
      { target: { value: "7" } },
    );
    // Stock Update left blank → not sent (use framework default).
    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const patch = onSave.mock.calls[0][0];
    expect(patch.web_search_budgets_by_mode).toEqual({ stock_initiation: 7 });
  });

  it("rejects non-digit characters at the input boundary", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    const input = screen.getByLabelText(
      "Web search budget for Stock Initiation",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "abc" } });
    expect(input.value).toBe("");
    fireEvent.change(input, { target: { value: "12" } });
    expect(input.value).toBe("12");
    fireEvent.change(input, { target: { value: "12x" } });
    // Invalid keystroke ignored — value stays "12".
    expect(input.value).toBe("12");
  });
});
