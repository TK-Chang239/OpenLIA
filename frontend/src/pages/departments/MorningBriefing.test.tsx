import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import MorningBriefing from "./MorningBriefing";

vi.mock("../../hooks/useMbConfig", () => ({
  useMbConfig: () => ({
    config: {
      report_length: "normal",
      enabled_section_ids: [],
      section_topics: {},
      custom_sections: [],
      reference_portfolio: false,
    },
    save: vi.fn().mockResolvedValue(undefined),
    loading: false,
  }),
}));

vi.mock("../../hooks/useMbSchedules", () => ({
  useMbSchedules: () => ({
    schedules: [],
    loading: false,
    create: vi.fn().mockResolvedValue(undefined),
    update: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../../hooks/useMbReports", () => ({
  useMbReports: () => ({
    reports: [
      {
        id: "r-1",
        title: "Morning Briefing 2026-04-24",
        report_type: "morning_briefing",
        created_at: "2026-04-24T13:00:00Z",
      },
    ],
    loading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../../components/morning-briefing/ModelPicker", () => ({
  ModelPicker: () => <select data-testid="mb-model-picker" />,
}));

vi.mock("../../components/report/ReportRenderer", () => ({
  ReportRenderer: (props: { schema: { cover: { title: string } } }) => (
    <div data-testid="report-renderer">{props.schema.cover.title}</div>
  ),
}));

vi.mock("../../api/reports", () => ({
  fetchReport: vi.fn().mockResolvedValue({
    schema_version: "2.0",
    department: "morning_briefing",
    generated_at: "2026-04-24T13:00:00Z",
    cover: { title: "Morning Briefing", subtitle: "", tagline: "" },
    sections: [{ id: "macro", title: "Macro", blocks: [] }],
  }),
  reportPdfUrl: (id: string) => `/api/reports/${id}/export/pdf`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <FileViewerProvider>
        <MorningBriefing />
      </FileViewerProvider>
    </MemoryRouter>,
  );
}

describe("MorningBriefing page", () => {
  it("renders Archive | Run Now | Schedule | Settings tabs (no Chat); ModelPicker lives on Run Now / Settings", () => {
    renderPage();
    expect(screen.getByText(/Morning Briefings/i)).toBeInTheDocument();
    expect(screen.getByText(/Morning Briefing 2026-04-24/)).toBeInTheDocument();
    // Tabs
    expect(screen.getByRole("button", { name: /^Archive$/ })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Run Now$/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Schedule$/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Settings$/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Chat$/ }),
    ).not.toBeInTheDocument();
    // ModelPicker not shown on Archive
    expect(screen.queryByTestId("mb-model-picker")).not.toBeInTheDocument();
    // Switch to Settings — ModelPicker should appear
    fireEvent.click(screen.getByRole("button", { name: /^Settings$/ }));
    expect(screen.getByTestId("mb-model-picker")).toBeInTheDocument();
  });

  it("opening a briefing shows the viewer with ReportRenderer (no inline chat)", async () => {
    renderPage();
    fireEvent.click(screen.getByTestId("mb-hero-open"));
    await waitFor(() =>
      expect(screen.getByTestId("mb-viewer")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Follow-up chat/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("report-renderer")).toBeInTheDocument();
    expect(
      screen.getByTestId("mb-ask-in-secretary"),
    ).toBeInTheDocument();
  });

  it("Close button returns to the archive", async () => {
    renderPage();
    fireEvent.click(screen.getByTestId("mb-hero-open"));
    await waitFor(() =>
      expect(screen.getByTestId("mb-viewer")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Close$/ }));
    await waitFor(() =>
      expect(screen.queryByTestId("mb-viewer")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/Morning Briefing 2026-04-24/)).toBeInTheDocument();
  });
});
