import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReportCard } from "./ReportCard";

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
    render(
      <ReportCard
        {...baseProps}
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />,
    );
    expect(screen.getByText(/stock update report/i)).toBeInTheDocument();
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
  });

  it("calls onOpen when Open Report is clicked", () => {
    const onOpen = vi.fn();
    render(
      <ReportCard
        {...baseProps}
        onOpen={onOpen}
        onDownload={() => {}}
        onSave={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /open report/i }));
    expect(onOpen).toHaveBeenCalledWith("r1");
  });

  it("renders sector research label without companyName", () => {
    render(
      <ReportCard
        reportId="r2"
        mode="sector_research"
        subject="Semiconductors"
        companyName={null}
        createdAt="2026-04-09T12:00:00Z"
        preview="x"
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />,
    );
    expect(screen.getByText(/sector research report/i)).toBeInTheDocument();
    expect(screen.getByText(/Semiconductors/)).toBeInTheDocument();
  });

  it("Download dropdown shows PDF and DOCX items (NEW-14-04)", async () => {
    const user = userEvent.setup();
    render(
      <ReportCard
        {...baseProps}
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />,
    );
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
    render(
      <ReportCard
        {...baseProps}
        onOpen={() => {}}
        onDownload={onDownload}
        onSave={() => {}}
      />,
    );
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
    render(
      <ReportCard
        {...baseProps}
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={onSave}
      />,
    );
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
});
