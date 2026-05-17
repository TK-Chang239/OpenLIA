import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ReportCard } from "./ReportCard";
import * as chatApi from "../../api/chat";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderCard(props: React.ComponentProps<typeof ReportCard>) {
  return render(
    <MemoryRouter>
      <ReportCard {...props} />
    </MemoryRouter>,
  );
}

const baseProps = {
  reportId: "r1",
  mode: "stock_update" as const,
  subject: "AAPL",
  companyName: "Apple Inc.",
  createdAt: "2026-04-09T12:00:00Z",
  preview: "Apple reported...",
};

describe("ReportCard", () => {
  it("renders the mode title and subject line", () => {
    renderCard({
      ...baseProps,
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
    });
    expect(screen.getByText(/stock update report/i)).toBeInTheDocument();
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
  });

  it("calls onOpen when Open Report is clicked", () => {
    const onOpen = vi.fn();
    renderCard({
      ...baseProps,
      onOpen,
      onDownload: () => {},
      onSave: () => {},
    });
    fireEvent.click(screen.getByRole("button", { name: /open report/i }));
    expect(onOpen).toHaveBeenCalledWith("r1");
  });

  it("renders sector research label without companyName", () => {
    renderCard({
      reportId: "r2",
      mode: "sector_research",
      subject: "Semiconductors",
      companyName: null,
      createdAt: "2026-04-09T12:00:00Z",
      preview: "x",
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
    });
    expect(screen.getByText(/sector research report/i)).toBeInTheDocument();
    expect(screen.getByText(/Semiconductors/)).toBeInTheDocument();
  });

  it("Download dropdown shows PDF and DOCX items (NEW-14-04)", async () => {
    const user = userEvent.setup();
    renderCard({
      ...baseProps,
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
    });
    await user.click(screen.getByRole("button", { name: /^download$/i }));
    await waitFor(() => {
      expect(
        screen.getByRole("menuitem", { name: /download as pdf/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("menuitem", { name: /download as docx/i }),
      ).toBeInTheDocument();
    });
  });

  it("clicking Download as DOCX invokes onDownload with format=docx", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    renderCard({
      ...baseProps,
      onOpen: () => {},
      onDownload,
      onSave: () => {},
    });
    await user.click(screen.getByRole("button", { name: /^download$/i }));
    const docxItem = await screen.findByRole("menuitem", {
      name: /download as docx/i,
    });
    await user.click(docxItem);
    await waitFor(() => {
      expect(onDownload).toHaveBeenCalledWith("r1", "docx");
    });
  });

  it("clicking Save flips the bookmark to saved (NEW-14-05)", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const recentCreatedAt = new Date(Date.now() - 86_400_000).toISOString();
    renderCard({
      ...baseProps,
      createdAt: recentCreatedAt,
      onOpen: () => {},
      onDownload: () => {},
      onSave,
    });
    const saveBtn = screen.getByRole("button", { name: /save to repo/i });
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("r1");
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /saved to repo/i }),
      ).toBeInTheDocument();
    });
  });

  it("renders tombstone variant when expiredAt is set", () => {
    renderCard({
      ...baseProps,
      expiredAt: "2026-05-15T12:00:00Z",
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
    });
    expect(screen.getByTestId("er-report-card-tombstone")).toBeInTheDocument();
    expect(screen.getByText(/no longer available/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open report/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /save to repo/i })).toBeNull();
  });

  it("clicking Saved when within 7 days calls onUnsave (soft remove)", async () => {
    const recentCreatedAt = new Date(Date.now() - 86_400_000).toISOString();
    const onUnsave = vi.fn().mockResolvedValue(undefined);
    renderCard({
      ...baseProps,
      createdAt: recentCreatedAt,
      initialSaved: true,
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
      onUnsave,
    });
    const savedBtn = screen.getByRole("button", { name: /saved to repository/i });
    fireEvent.click(savedBtn);
    await waitFor(() => {
      expect(onUnsave).toHaveBeenCalledWith("r1");
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save to repository/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows Delete button instead of bookmark when saved and age >= 7 days", () => {
    const oldCreatedAt = new Date(Date.now() - 8 * 86_400_000).toISOString();
    renderCard({
      ...baseProps,
      createdAt: oldCreatedAt,
      initialSaved: true,
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
      onDelete: vi.fn(),
    });
    expect(
      screen.getByRole("button", { name: /delete report/i }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("bookmark-icon")).toBeNull();
  });

  it("Delete button opens confirm dialog and dispatches onDelete on confirm", async () => {
    const oldCreatedAt = new Date(Date.now() - 8 * 86_400_000).toISOString();
    const onDelete = vi.fn().mockResolvedValue(undefined);
    renderCard({
      ...baseProps,
      createdAt: oldCreatedAt,
      initialSaved: true,
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
      onDelete,
    });
    fireEvent.click(screen.getByRole("button", { name: /delete report/i }));
    expect(screen.getByTestId("delete-report-dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledWith("r1");
    });
  });

  it("shows a Discuss button and navigates to the returned chat session on click", async () => {
    mockNavigate.mockClear();
    const createSpy = vi
      .spyOn(chatApi, "createSession")
      .mockResolvedValue({ id: "sess_new", attached_report_id: "r1" } as any);
    renderCard({
      ...baseProps,
      onOpen: () => {},
      onDownload: () => {},
      onSave: () => {},
    });
    fireEvent.click(screen.getByRole("button", { name: /discuss/i }));
    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith({
        department: "equity_research",
        title: "AAPL",
        attached_report_id: "r1",
      }),
    );
    expect(mockNavigate).toHaveBeenCalledWith("/chat/sess_new");
  });
});
