import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

vi.mock("../../hooks/useMbSchedule", () => ({
  useMbSchedule: () => ({
    schedule: null,
    save: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
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

vi.mock("../../hooks/useMbChatSession", () => ({
  useMbChatSession: () => ({ sessionId: "sess-mb-1", error: null }),
}));

vi.mock("../../components/chat/ChatInterface", () => ({
  ChatInterface: (props: {
    sessionId: string;
    inputPlaceholder: string;
  }) => (
    <div
      data-testid="chat-interface"
      data-session-id={props.sessionId}
      data-placeholder={props.inputPlaceholder}
    />
  ),
}));

vi.mock("../../components/report/ReportRenderer", () => ({
  ReportRenderer: (props: { schema: { cover: { title: string } } }) => (
    <div data-testid="report-renderer">{props.schema.cover.title}</div>
  ),
}));

vi.mock("../../api/reports", () => ({
  fetchReport: vi.fn().mockResolvedValue({
    schema_version: "1.0",
    department: "morning_briefing",
    generated_at: "2026-04-24T13:00:00Z",
    cover: { title: "Morning Briefing", subtitle: "", tagline: "" },
    sections: [{ id: "macro", title: "Macro", blocks: [] }],
  }),
  reportPdfUrl: (id: string) => `/api/reports/${id}/export/pdf`,
}));

function renderPage() {
  return render(
    <FileViewerProvider>
      <MorningBriefing />
    </FileViewerProvider>,
  );
}

describe("MorningBriefing page", () => {
  it("renders header, archive list, and all three tabs", () => {
    renderPage();
    expect(screen.getByText(/Morning Briefings/i)).toBeInTheDocument();
    expect(screen.getByText(/Morning Briefing 2026-04-24/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Archive$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Chat$/ })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Settings$/ }),
    ).toBeInTheDocument();
  });

  it("Chat tab mounts ChatInterface bound to the MB session", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /^Chat$/ }));
    const chat = screen.getByTestId("chat-interface");
    expect(chat).toHaveAttribute("data-session-id", "sess-mb-1");
    expect(chat).toHaveAttribute(
      "data-placeholder",
      expect.stringContaining("Morning Briefings") as unknown as string,
    );
  });

  it("opening a briefing shows the viewer with ReportRenderer + follow-up chat", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /^Open$/ }));
    await waitFor(() =>
      expect(screen.getByTestId("mb-viewer")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Follow-up chat/i)).toBeInTheDocument();
    const chat = screen.getByTestId("chat-interface");
    expect(chat).toHaveAttribute("data-session-id", "sess-mb-1");
    expect(chat).toHaveAttribute(
      "data-placeholder",
      expect.stringContaining("follow-up") as unknown as string,
    );
  });

  it("Close button returns to the archive", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /^Open$/ }));
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
