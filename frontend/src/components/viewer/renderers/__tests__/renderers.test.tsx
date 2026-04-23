import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MarkdownRenderer } from "../MarkdownRenderer";
import { CodeRenderer } from "../CodeRenderer";
import { CsvRenderer } from "../CsvRenderer";
import { ImageRenderer } from "../ImageRenderer";
import { UnsupportedRenderer } from "../UnsupportedRenderer";

function mockFetchText(body: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      text: async () => body,
    }),
  );
}

describe("renderers", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("Markdown renders headings and paragraphs", async () => {
    mockFetchText("# Hello\n\nThis is content.");
    render(<MarkdownRenderer source={{ kind: "report", reportId: "1" }} />);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Hello" })).toBeInTheDocument(),
    );
  });

  it("Code renders monospace body with line numbers", async () => {
    mockFetchText("line1\nline2");
    render(<CodeRenderer source={{ kind: "report", reportId: "1" }} />);
    await waitFor(() => expect(screen.getByText(/line1/)).toBeInTheDocument());
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("CSV renders table with header and rows", async () => {
    mockFetchText("a,b\n1,2\n3,4");
    render(<CsvRenderer source={{ kind: "report", reportId: "1" }} />);
    await waitFor(() => expect(screen.getByText("a")).toBeInTheDocument());
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("Image renders <img> with download URL", () => {
    render(<ImageRenderer source={{ kind: "attachment", attachmentId: "7" }} />);
    const img = screen.getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("/api/chat/attachments/7/download");
  });

  it("Unsupported shows message + download link", () => {
    render(<UnsupportedRenderer source={{ kind: "report", reportId: "5" }} filename="x.exe" />);
    expect(screen.getByText(/preview not available/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /download/i })).toHaveAttribute(
      "href",
      "/api/reports/5/download",
    );
  });
});
