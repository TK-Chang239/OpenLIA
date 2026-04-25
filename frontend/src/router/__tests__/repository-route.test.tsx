import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../../api/repo", () => ({
  listRepoItemsFiltered: vi.fn().mockResolvedValue({
    items: [],
    page: 1,
    page_size: 50,
    has_more: false,
  }),
  fetchRepoFacets: vi.fn().mockResolvedValue({ departments: [], total: 0 }),
  saveToRepo: vi.fn(),
  unsaveFromRepo: vi.fn(),
}));

vi.mock("../../api/reports", () => ({ reportPdfUrl: (id: string) => `/api/reports/${id}/pdf` }));

import Repository from "../../pages/Repository";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import { ToastProvider } from "../../components/primitives/Toast";

describe("/repository route smoke", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("navigates to /repository and renders page header", async () => {
    render(
      <MemoryRouter initialEntries={["/repository"]}>
        <ToastProvider>
          <FileViewerProvider>
            <Routes>
              <Route path="/repository" element={<Repository />} />
            </Routes>
          </FileViewerProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Repository/ })).toBeInTheDocument(),
    );
  });

  it("nav data includes a Repository entry pointing at /repository", async () => {
    const navData = await import("../../components/sidebar/navData");
    const repo = navData.CORE_NAV.find((e) => e.id === "repository");
    expect(repo).toBeDefined();
    expect(repo?.path).toBe("/repository");
    expect(repo?.label).toBe("Repository");
  });
});
