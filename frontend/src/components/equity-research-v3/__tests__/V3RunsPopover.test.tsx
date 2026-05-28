import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as api from "../../../api/equity-research-v3";
import { V3RunsPopover } from "../V3RunsPopover";

vi.mock("../../../api/equity-research-v3", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    listV3Runs: vi.fn(),
    deleteV3Run: vi.fn(),
  };
});

const ROWS: api.V3ReportSummary[] = [
  {
    report_id: "run-1",
    subject: "RKLB.US",
    template_id: "initiation",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-05-27T10:00:00Z",
    completed_at: "2026-05-27T10:05:00Z",
  },
  {
    report_id: "run-2",
    subject: "AAPL deep dive",
    template_id: "initiation",
    language: "en",
    length: "normal",
    status: "running",
    created_at: "2026-05-27T11:00:00Z",
    completed_at: null,
  },
];

beforeEach(() => {
  vi.mocked(api.listV3Runs).mockResolvedValue(ROWS);
  vi.mocked(api.deleteV3Run).mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("V3RunsPopover", () => {
  test("lists v3 runs and selects on click", async () => {
    const onSelect = vi.fn();
    render(
      <V3RunsPopover
        activeSessionId={null}
        onSelect={onSelect}
        onActiveDeleted={() => undefined}
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("RKLB.US")).toBeInTheDocument();
    });
    expect(screen.getByText("AAPL deep dive")).toBeInTheDocument();

    fireEvent.click(screen.getByText("RKLB.US"));
    expect(onSelect).toHaveBeenCalledWith("run-1");
  });

  test("filters by subject via the search box", async () => {
    render(
      <V3RunsPopover
        activeSessionId={null}
        onSelect={() => undefined}
        onActiveDeleted={() => undefined}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("RKLB.US")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Search v3 runs"), {
      target: { value: "aapl" },
    });

    await waitFor(() => {
      expect(screen.queryByText("RKLB.US")).toBeNull();
      expect(screen.getByText("AAPL deep dive")).toBeInTheDocument();
    });
  });

  test("renders empty state when no runs", async () => {
    vi.mocked(api.listV3Runs).mockResolvedValue([]);
    render(
      <V3RunsPopover
        activeSessionId={null}
        onSelect={() => undefined}
        onActiveDeleted={() => undefined}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("No v3 runs yet.")).toBeInTheDocument();
    });
  });

  test("calls onActiveDeleted when the active run is deleted", async () => {
    const onActiveDeleted = vi.fn();
    render(
      <V3RunsPopover
        activeSessionId="run-1"
        onSelect={() => undefined}
        onActiveDeleted={onActiveDeleted}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("RKLB.US")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText("Delete run RKLB.US"));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(api.deleteV3Run).toHaveBeenCalledWith("run-1");
      expect(onActiveDeleted).toHaveBeenCalledTimes(1);
    });
  });
});
