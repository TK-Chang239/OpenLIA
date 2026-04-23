import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { FileDownloadButton } from "../FileDownloadButton";

describe("FileDownloadButton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders chip variant with download icon and no label", () => {
    render(<FileDownloadButton url="/f/1" filename="report.pdf" variant="chip" />);
    const btn = screen.getByRole("button", { name: /download report\.pdf/i });
    expect(btn.textContent?.trim()).toBe("");
  });

  it("renders viewer-header variant with a visible label", () => {
    render(<FileDownloadButton url="/f/1" filename="report.pdf" variant="viewer-header" />);
    expect(screen.getByRole("button", { name: /download/i })).toHaveTextContent(/download/i);
  });

  it("invokes the click handler and shows a temporary success indicator", async () => {
    const onTrigger = vi.fn();
    render(
      <FileDownloadButton
        url="/f/1"
        filename="report.pdf"
        variant="viewer-header"
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /download/i }));
    expect(onTrigger).toHaveBeenCalledWith("/f/1", "report.pdf");
    expect(screen.getByTestId("download-success")).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(1500); });
    expect(screen.queryByTestId("download-success")).not.toBeInTheDocument();
  });

  it("shows a temporary error indicator when onTrigger throws", async () => {
    const onTrigger = vi.fn(() => {
      throw new Error("boom");
    });
    render(
      <FileDownloadButton
        url="/f/1"
        filename="report.pdf"
        variant="viewer-header"
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /download/i }));
    expect(screen.getByTestId("download-error")).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.queryByTestId("download-error")).not.toBeInTheDocument();
  });
});
