import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as api from "../../../api/equity-research-v3";
import { ApiError } from "../../../api/_request";
import { V3RevisionChat } from "../V3RevisionChat";

vi.mock("../../../api/equity-research-v3", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    listV3Revisions: vi.fn(),
    startV3Revision: vi.fn(),
    cancelV3Revision: vi.fn(),
  };
});

const COMPLETED_REV: api.V3Revision = {
  id: "rev-1",
  report_id: "rpt-1",
  revision_index: 1,
  request: "Rewrite the bull case to lead with EBITDA.",
  status: "completed",
  error_message: null,
  created_at: "2026-05-27T10:00:00Z",
  completed_at: "2026-05-27T10:01:00Z",
};

const RUNNING_REV: api.V3Revision = {
  ...COMPLETED_REV,
  id: "rev-2",
  revision_index: 2,
  request: "Add a competitor analysis section.",
  status: "running",
  completed_at: null,
};

beforeEach(() => {
  vi.mocked(api.listV3Revisions).mockResolvedValue([]);
  vi.mocked(api.startV3Revision).mockResolvedValue({ revision_id: "rev-new" });
  vi.mocked(api.cancelV3Revision).mockResolvedValue({ cancelled: true });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("V3RevisionChat", () => {
  test("renders empty state when no revisions exist", async () => {
    render(
      <V3RevisionChat reportId="rpt-1" onRevisionComplete={() => undefined} />,
    );
    await waitFor(() => {
      expect(screen.getByText("No revisions yet.")).toBeInTheDocument();
    });
  });

  test("lists past revisions with status badges", async () => {
    vi.mocked(api.listV3Revisions).mockResolvedValue([COMPLETED_REV]);
    render(
      <V3RevisionChat reportId="rpt-1" onRevisionComplete={() => undefined} />,
    );
    await waitFor(() => {
      expect(
        screen.getByText("Rewrite the bull case to lead with EBITDA."),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  test("submitting posts to startV3Revision", async () => {
    render(
      <V3RevisionChat reportId="rpt-1" onRevisionComplete={() => undefined} />,
    );
    await waitFor(() => expect(api.listV3Revisions).toHaveBeenCalled());

    fireEvent.change(screen.getByTestId("er-v3-revision-input"), {
      target: { value: "tighten the valuation section" },
    });
    fireEvent.click(screen.getByTestId("er-v3-revision-send"));

    await waitFor(() => {
      expect(api.startV3Revision).toHaveBeenCalledWith("rpt-1", {
        request: "tighten the valuation section",
      });
    });
  });

  test("surfaces 409 conflict as a friendly error", async () => {
    vi.mocked(api.startV3Revision).mockRejectedValue(
      new ApiError(409, "Another revision is in flight"),
    );
    render(
      <V3RevisionChat reportId="rpt-1" onRevisionComplete={() => undefined} />,
    );
    await waitFor(() => expect(api.listV3Revisions).toHaveBeenCalled());

    fireEvent.change(screen.getByTestId("er-v3-revision-input"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByTestId("er-v3-revision-send"));

    await waitFor(() => {
      expect(screen.getByTestId("er-v3-revision-error")).toHaveTextContent(
        /Another revision is already in flight/,
      );
    });
  });

  test("disables composer when parent is still running", async () => {
    render(
      <V3RevisionChat
        reportId="rpt-1"
        parentRunning
        onRevisionComplete={() => undefined}
      />,
    );
    await waitFor(() => expect(api.listV3Revisions).toHaveBeenCalled());

    const input = screen.getByTestId("er-v3-revision-input") as HTMLTextAreaElement;
    expect(input.placeholder).toContain("Wait for the initial run");
    const send = screen.getByTestId("er-v3-revision-send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
  });

  test("Cancel button on a running revision calls cancelV3Revision", async () => {
    vi.mocked(api.listV3Revisions).mockResolvedValue([RUNNING_REV]);
    render(
      <V3RevisionChat reportId="rpt-1" onRevisionComplete={() => undefined} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Add a competitor analysis section.")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`er-v3-revision-cancel-${RUNNING_REV.id}`));
    await waitFor(() => {
      expect(api.cancelV3Revision).toHaveBeenCalledWith(RUNNING_REV.id);
    });
  });

  test("fires onRevisionComplete when a running revision flips terminal", async () => {
    // First poll returns running; second poll returns completed.
    const onComplete = vi.fn();
    vi.mocked(api.listV3Revisions)
      .mockResolvedValueOnce([RUNNING_REV])
      .mockResolvedValue([{ ...RUNNING_REV, status: "completed" }]);
    vi.useFakeTimers();
    render(
      <V3RevisionChat reportId="rpt-1" onRevisionComplete={onComplete} />,
    );
    // Initial mount fetch — flush the microtask + timer queue
    await vi.runOnlyPendingTimersAsync();
    // Advance 2s to trigger the poll interval
    await vi.advanceTimersByTimeAsync(2100);
    await vi.runOnlyPendingTimersAsync();
    expect(onComplete).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
