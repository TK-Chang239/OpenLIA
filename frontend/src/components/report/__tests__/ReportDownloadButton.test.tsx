import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const downloadReportBlob = vi.fn();
const triggerBrowserSave = vi.fn();

vi.mock("../../../api/reports", async () => {
  const actual = await vi.importActual<typeof import("../../../api/reports")>(
    "../../../api/reports",
  );
  return {
    ...actual,
    downloadReportBlob: (...args: unknown[]) =>
      (downloadReportBlob as unknown as (...a: unknown[]) => unknown)(...args),
    triggerBrowserSave: (...args: unknown[]) =>
      (triggerBrowserSave as unknown as (...a: unknown[]) => unknown)(...args),
  };
});

const pushToast = vi.fn();
vi.mock("../../primitives/Toast", () => ({
  useToast: () => ({ toasts: [], push: pushToast, dismiss: vi.fn() }),
}));

import { ReportDownloadButton } from "../ReportDownloadButton";

describe("ReportDownloadButton", () => {
  beforeEach(() => {
    downloadReportBlob.mockReset();
    triggerBrowserSave.mockReset();
    pushToast.mockReset();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("downloads as PDF when PDF option clicked", async () => {
    downloadReportBlob.mockResolvedValue({
      blob: new Blob(["pdf"]),
      filename: "AAPL.pdf",
    });
    const user = userEvent.setup();
    render(<ReportDownloadButton reportId="abc" />);
    await user.click(screen.getByRole("button", { name: /download/i }));
    await user.click(await screen.findByRole("menuitem", { name: /pdf/i }));
    await waitFor(() => {
      expect(downloadReportBlob).toHaveBeenCalledWith("abc", "pdf");
      expect(triggerBrowserSave).toHaveBeenCalledWith(
        expect.any(Blob),
        "AAPL.pdf",
      );
    });
  });

  it("hides the Word option when feature flag is off", async () => {
    vi.stubEnv("VITE_REPORT_DOCX_ENABLED", "false");
    const user = userEvent.setup();
    render(<ReportDownloadButton reportId="abc" />);
    await user.click(screen.getByRole("button", { name: /download/i }));
    expect(screen.queryByRole("menuitem", { name: /word/i })).toBeNull();
  });

  it("pushes an error toast on download failure", async () => {
    downloadReportBlob.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(<ReportDownloadButton reportId="abc" />);
    await user.click(screen.getByRole("button", { name: /download/i }));
    await user.click(await screen.findByRole("menuitem", { name: /pdf/i }));
    await waitFor(() => {
      expect(pushToast).toHaveBeenCalledWith(
        expect.objectContaining({ tone: "error" }),
      );
    });
  });

  it("disables the button while a download is in flight", async () => {
    let resolve!: (value: { blob: Blob; filename: string }) => void;
    downloadReportBlob.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const user = userEvent.setup();
    render(<ReportDownloadButton reportId="abc" />);
    const trigger = screen.getByRole("button", { name: /download/i });
    await user.click(trigger);
    await user.click(await screen.findByRole("menuitem", { name: /pdf/i }));
    await waitFor(() => expect(trigger).toBeDisabled());
    resolve({ blob: new Blob(["x"]), filename: "x.pdf" });
    await waitFor(() => expect(trigger).not.toBeDisabled());
  });
});
