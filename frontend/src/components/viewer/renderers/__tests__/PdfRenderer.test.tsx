import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { PdfRenderer } from "../PdfRenderer";

vi.mock("pdfjs-dist", () => ({
  getDocument: () => ({
    promise: Promise.resolve({
      numPages: 3,
      getPage: vi.fn().mockResolvedValue({
        getViewport: () => ({ width: 100, height: 100 }),
        render: () => ({ promise: Promise.resolve() }),
      }),
    }),
  }),
  GlobalWorkerOptions: { workerSrc: "" },
}));

describe("PdfRenderer", () => {
  it("renders a page navigator", async () => {
    render(<PdfRenderer source={{ kind: "attachment", attachmentId: "9" }} />);
    expect(await screen.findByText(/page 1 of 3/i)).toBeInTheDocument();
  });
});
