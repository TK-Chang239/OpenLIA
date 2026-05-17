import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("pdfjs-dist", () => ({
  getDocument: () => ({ promise: Promise.resolve({ numPages: 0, getPage: vi.fn() }) }),
  GlobalWorkerOptions: { workerSrc: "" },
}));

vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  type AnyProps = Record<string, unknown> & { children?: React.ReactNode };
  const stripFmProps = (props: AnyProps) => {
    const {
      initial: _i,
      animate: _a,
      exit: _e,
      transition: _t,
      whileHover: _w,
      ...rest
    } = props;
    return rest;
  };
  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    motion: {
      ...actual.motion,
      aside: ({ children, ...props }: AnyProps) => (
        <aside {...stripFmProps(props)}>{children}</aside>
      ),
      div: ({ children, ...props }: AnyProps) => (
        <div {...stripFmProps(props)}>{children}</div>
      ),
      button: ({ children, ...props }: AnyProps) => (
        <button {...stripFmProps(props)}>{children}</button>
      ),
    },
    useReducedMotion: () => false,
  };
});

const listRepoItemsFiltered = vi.fn();
const fetchRepoFacets = vi.fn();
const saveToRepo = vi.fn();
const unsaveFromRepo = vi.fn();
const deleteReport = vi.fn();

vi.mock("../../api/repo", async () => {
  return {
    listRepoItemsFiltered: (...a: unknown[]) => listRepoItemsFiltered(...a),
    fetchRepoFacets: (...a: unknown[]) => fetchRepoFacets(...a),
    saveToRepo: (...a: unknown[]) => saveToRepo(...a),
    unsaveFromRepo: (...a: unknown[]) => unsaveFromRepo(...a),
  };
});

vi.mock("../../api/reports", () => ({
  reportPdfUrl: (id: string) => `/api/reports/${id}/export/pdf`,
  deleteReport: (...a: unknown[]) => deleteReport(...a),
}));

import Repository from "../Repository";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import { FileViewer } from "../../components/viewer/FileViewer";
import { ToastProvider } from "../../components/primitives/Toast";

function renderPage(initial: string = "/repository") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <ToastProvider>
        <FileViewerProvider>
          <Repository />
          <FileViewer />
        </FileViewerProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

// Recent dates: within the 7-day retention window so the existing tests
// exercise the soft-remove path. A separate test below covers the
// post-retention "Delete" path with an explicitly old row.
const SAMPLE_ROW = {
  id: "i1",
  report_id: "r1",
  department: "equity_research",
  title: "AAPL",
  filename: "AAPL.pdf",
  generated_at: new Date(Date.now() - 86_400_000).toISOString(),
  saved_at: new Date(Date.now() - 3_600_000).toISOString(),
};

describe("Repository page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchRepoFacets.mockResolvedValue({
      departments: [{ slug: "equity_research", count: 1 }],
      total: 1,
    });
    listRepoItemsFiltered.mockResolvedValue({
      items: [SAMPLE_ROW],
      page: 1,
      page_size: 50,
      has_more: false,
    });
  });

  it("renders saved row and department badge", async () => {
    renderPage();
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    expect(await screen.findByText("AAPL.pdf")).toBeInTheDocument();
    expect(screen.getByTestId("department-badge")).toHaveTextContent("Equity Research");
  });

  it("shows no-saved empty state when zero rows and no filters", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({ items: [], page: 1, page_size: 50, has_more: false });
    fetchRepoFacets.mockResolvedValueOnce({ departments: [], total: 0 });
    renderPage();
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    expect(await screen.findByTestId("repo-empty-no-saved")).toBeInTheDocument();
  });

  it("opens remove dialog and removes row on confirm", async () => {
    unsaveFromRepo.mockResolvedValueOnce(undefined);
    renderPage();
    const removeBtn = await screen.findByRole("button", { name: /Remove AAPL.pdf/ });
    fireEvent.click(removeBtn);
    expect(await screen.findByTestId("remove-confirm-dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Remove$/ }));
    await waitFor(() => expect(unsaveFromRepo).toHaveBeenCalledWith("r1"));
    await waitFor(() => expect(screen.queryByText("AAPL.pdf")).not.toBeInTheDocument());
  });

  it("clicking row opens FileViewer with metadata and no Save button", async () => {
    renderPage();
    const row = await screen.findByTestId("repo-row");
    fireEvent.click(row);
    const viewer = await screen.findByTestId("file-viewer");
    expect(viewer).toBeInTheDocument();
    // Save-to-Repo button must NOT render in viewer header.
    expect(
      viewer.querySelector('[aria-label="Save to repository"]'),
    ).toBeNull();
    expect(
      viewer.querySelector('[aria-label="Remove from repository"]'),
    ).toBeNull();
  });

  it("Download button click does not open viewer", async () => {
    renderPage();
    const dl = await screen.findByRole("button", { name: /download report/i });
    fireEvent.click(dl);
    expect(screen.queryByTestId("file-viewer")).not.toBeInTheDocument();
  });

  it("changes sort and fires fetch with new sort param", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    listRepoItemsFiltered.mockClear();
    await user.click(screen.getByRole("button", { name: /Sort/ }));
    await user.click(await screen.findByText("Filename (A→Z)"));
    await waitFor(() =>
      expect(listRepoItemsFiltered).toHaveBeenCalledWith(
        expect.objectContaining({ sort: "filename_asc" }),
      ),
    );
  });

  it("URL params restore filters", async () => {
    renderPage("/repository?q=aapl&department=equity_research");
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    expect(screen.getByLabelText(/Search filename/)).toHaveValue("aapl");
  });

  it("Clear all removes filters and resets URL", async () => {
    renderPage("/repository?q=aapl");
    await waitFor(() => expect(screen.getByText(/Search:/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Clear all"));
    await waitFor(() => expect(screen.queryByText(/Search:/)).not.toBeInTheDocument());
  });

  it("filter chip dismiss removes that filter", async () => {
    renderPage("/repository?department=equity_research");
    const chip = await screen.findByRole("button", {
      name: /Remove filter Department: Equity Research/,
    });
    fireEvent.click(chip);
    await waitFor(() =>
      expect(
        screen.queryByText("Department: Equity Research", {
          selector: "[data-testid='filter-chip'] *",
        }),
      ).not.toBeInTheDocument(),
    );
  });

  it("error state renders the error alert", async () => {
    listRepoItemsFiltered.mockRejectedValueOnce(new Error("boom"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("undo restores row at original index after successful remove", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [
        SAMPLE_ROW,
        { ...SAMPLE_ROW, id: "i2", report_id: "r2", filename: "MSFT.pdf" },
        { ...SAMPLE_ROW, id: "i3", report_id: "r3", filename: "GOOG.pdf" },
      ],
      page: 1,
      page_size: 50,
      has_more: false,
    });
    unsaveFromRepo.mockResolvedValueOnce(undefined);
    saveToRepo.mockResolvedValueOnce({ id: "i2", report_id: "r2", created_at: "" });
    renderPage();
    const removeBtn = await screen.findByRole("button", { name: /Remove MSFT.pdf/ });
    fireEvent.click(removeBtn);
    fireEvent.click(screen.getByRole("button", { name: /^Remove$/ }));
    await waitFor(() => expect(unsaveFromRepo).toHaveBeenCalledWith("r2"));
    const undo = await screen.findByRole("button", { name: /Undo/ });
    await act(async () => {
      undo.click();
    });
    await waitFor(() => expect(saveToRepo).toHaveBeenCalledWith("r2"));
    await waitFor(() => {
      const rows = screen.getAllByTestId("repo-row");
      expect(rows[1]).toHaveTextContent("MSFT.pdf");
    });
  });

  it("error toast appears when remove fails and row is restored", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [
        SAMPLE_ROW,
        { ...SAMPLE_ROW, id: "i2", report_id: "r2", filename: "MSFT.pdf" },
      ],
      page: 1,
      page_size: 50,
      has_more: false,
    });
    unsaveFromRepo.mockRejectedValueOnce(new Error("nope"));
    renderPage();
    const removeBtn = await screen.findByRole("button", { name: /Remove MSFT.pdf/ });
    fireEvent.click(removeBtn);
    fireEvent.click(screen.getByRole("button", { name: /^Remove$/ }));
    await waitFor(() => expect(screen.getByText(/Failed to remove/i)).toBeInTheDocument());
    // Row restored at original index.
    await waitFor(() => {
      const rows = screen.getAllByTestId("repo-row");
      expect(rows[1]).toHaveTextContent("MSFT.pdf");
    });
  });

  it("opens DeleteReportDialog and calls deleteReport for rows >= 7 days old", async () => {
    const OLD_ROW = {
      ...SAMPLE_ROW,
      id: "old1",
      report_id: "rOld",
      filename: "Old.pdf",
      generated_at: new Date(Date.now() - 8 * 86_400_000).toISOString(),
    };
    listRepoItemsFiltered.mockResolvedValue({
      items: [OLD_ROW],
      page: 1,
      page_size: 50,
      has_more: false,
    });
    deleteReport.mockResolvedValueOnce(undefined);
    renderPage();
    const removeBtn = await screen.findByRole("button", { name: /Remove Old.pdf/ });
    fireEvent.click(removeBtn);
    // The destructive DeleteReportDialog (not the soft RemoveConfirmDialog) opens.
    expect(screen.getByTestId("delete-report-dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(deleteReport).toHaveBeenCalledWith("rOld");
    });
    await waitFor(() => {
      expect(screen.getByText(/Report deleted permanently/i)).toBeInTheDocument();
    });
  });
});
