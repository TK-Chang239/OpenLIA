import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { FirstRunSummary } from "../FirstRunSummary";
import * as deptHealthApi from "../../../api/dept-health";

vi.mock("../../../api/dept-health", async () => {
  const actual = await vi.importActual<typeof deptHealthApi>(
    "../../../api/dept-health",
  );
  return {
    ...actual,
    fetchDeptHealth: vi.fn(),
    recheckDeptHealth: vi.fn(),
  };
});

const mocked = deptHealthApi as unknown as {
  fetchDeptHealth: ReturnType<typeof vi.fn>;
  recheckDeptHealth: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FirstRunSummary", () => {
  it("expands a disabled department to show missing categories and unresolved needs", async () => {
    mocked.fetchDeptHealth.mockResolvedValue([
      {
        department_id: "macro_research",
        status: "disabled",
        reason: "Missing required categories: financial",
        missing_categories: ["financial"],
        unresolved_needs: ["stock_quote"],
      },
    ]);
    render(<FirstRunSummary />);
    const toggle = await screen.findByTestId(
      "disabled-dept-macro_research-toggle",
    );
    fireEvent.click(toggle);
    const details = await screen.findByTestId(
      "disabled-dept-macro_research-details",
    );
    expect(details).toHaveTextContent(/Missing categories/);
    expect(details).toHaveTextContent(/financial/);
    expect(details).toHaveTextContent(/Unresolved needs/);
    expect(details).toHaveTextContent(/stock_quote/);
  });

  it("re-check button calls recheckDeptHealth and updates the list", async () => {
    mocked.fetchDeptHealth.mockResolvedValue([
      {
        department_id: "macro_research",
        status: "disabled",
        reason: "Missing required categories: financial",
        missing_categories: ["financial"],
        unresolved_needs: [],
      },
    ]);
    mocked.recheckDeptHealth.mockResolvedValue([
      {
        department_id: "macro_research",
        status: "active",
        reason: null,
        missing_categories: [],
        unresolved_needs: [],
      },
    ]);
    render(<FirstRunSummary />);
    await screen.findByText(/macro_research/);
    fireEvent.click(screen.getByTestId("dept-health-recheck"));
    await waitFor(() =>
      expect(mocked.recheckDeptHealth).toHaveBeenCalled(),
    );
    await waitFor(() =>
      expect(
        screen.queryByTestId("disabled-dept-macro_research"),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/Departments: 1 of 1 active/)).toBeInTheDocument();
  });

  it("re-check failure shows an error message", async () => {
    mocked.fetchDeptHealth.mockResolvedValue([]);
    mocked.recheckDeptHealth.mockRejectedValueOnce(new Error("boom"));
    render(<FirstRunSummary />);
    await screen.findByText(/Departments:/);
    fireEvent.click(screen.getByTestId("dept-health-recheck"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/boom/),
    );
  });

  it("does not render details when a disabled dept has no categories or needs", async () => {
    mocked.fetchDeptHealth.mockResolvedValue([
      {
        department_id: "panic_thermometer",
        status: "disabled",
        reason: "Missing required categories: financial",
        missing_categories: [],
        unresolved_needs: [],
      },
    ]);
    render(<FirstRunSummary />);
    await screen.findByText(/panic_thermometer/);
    expect(
      screen.queryByTestId("disabled-dept-panic_thermometer-toggle"),
    ).not.toBeInTheDocument();
  });
});
