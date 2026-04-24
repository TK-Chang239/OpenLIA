import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const listRepoItemsFiltered = vi.fn();
const fetchRepoFacets = vi.fn();
const saveToRepo = vi.fn();
const unsaveFromRepo = vi.fn();

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
}));

import Repository from "../Repository";

function renderPage() {
  return render(
    <MemoryRouter>
      <Repository />
    </MemoryRouter>,
  );
}

describe("Repository page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchRepoFacets.mockResolvedValue({
      departments: [{ slug: "equity_research", count: 1 }],
      total: 1,
    });
    listRepoItemsFiltered.mockResolvedValue({
      items: [
        {
          id: "i1",
          report_id: "r1",
          department: "equity_research",
          title: "AAPL",
          filename: "AAPL.pdf",
          generated_at: "2026-04-20T10:00:00Z",
          saved_at: "2026-04-22T10:00:00Z",
        },
      ],
      page: 1,
      page_size: 50,
      has_more: false,
    });
  });

  it("renders a saved report row and facet chip", async () => {
    renderPage();
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    expect(await screen.findByText("AAPL.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /equity_research \(1\)/ })).toBeInTheDocument();
  });

  it("shows empty state when no saved reports", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [],
      page: 1,
      page_size: 50,
      has_more: false,
    });
    fetchRepoFacets.mockResolvedValueOnce({ departments: [], total: 0 });
    renderPage();
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    expect(await screen.findByText(/No saved reports yet/)).toBeInTheDocument();
  });

  it("opens remove confirmation then deletes row", async () => {
    unsaveFromRepo.mockResolvedValueOnce(undefined);
    renderPage();
    const removeBtn = await screen.findByRole("button", { name: /Remove AAPL.pdf/ });
    fireEvent.click(removeBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Remove$/ }));
    await waitFor(() => expect(unsaveFromRepo).toHaveBeenCalledWith("r1"));
    await waitFor(() => expect(screen.queryByText("AAPL.pdf")).not.toBeInTheDocument());
  });
});
