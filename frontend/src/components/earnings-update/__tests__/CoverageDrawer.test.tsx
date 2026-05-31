import { describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { EuScheduleEntry, RunSummary, WatchlistEntry } from "../../../api/earnings-update";
import { CoverageDrawer } from "../CoverageDrawer";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o && "ticker" in o ? `${k}:${o.ticker}` : k,
  }),
}));

const NOW = Date.parse("2026-05-01T12:00:00Z");

function entry(t: string): WatchlistEntry {
  return { id: `e-${t}`, ticker: t, company_name: `${t} Inc.`, created_at: "2026-04-01T00:00:00Z" };
}
function run(t: string, status: RunSummary["status"]): RunSummary {
  return {
    report_id: `r-${t}`, ticker: t, subject: `${t} earnings`, template_id: "x",
    trigger_kind: "scheduled", fiscal_date: null, language: "en", length: "normal",
    status, created_at: "2026-04-30T00:00:00Z", completed_at: "2026-04-30T01:00:00Z", reasoning_effort: null,
  } as RunSummary;
}

function baseProps() {
  return {
    open: true,
    entries: [entry("AAPL"), entry("META")] as WatchlistEntry[],
    byTicker: new Map<string, EuScheduleEntry>(),
    runs: [run("AAPL", "running"), run("META", "completed")] as RunSummary[],
    now: NOW,
    onClose: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
  };
}

describe("CoverageDrawer", () => {
  test("renders bucket sections with the right tickers", () => {
    render(<CoverageDrawer {...baseProps()} />);
    expect(screen.getByTestId("coverage-bucket-live")).toHaveTextContent("AAPL");
    expect(screen.getByTestId("coverage-bucket-reported")).toHaveTextContent("META");
    expect(screen.queryByTestId("coverage-bucket-soon")).toBeNull();
  });

  test("stats strip shows Tracked count", () => {
    render(<CoverageDrawer {...baseProps()} />);
    expect(screen.getByTestId("coverage-stats")).toHaveTextContent("2");
  });

  test("add-ticker calls onAdd with the uppercased symbol", async () => {
    const props = baseProps();
    render(<CoverageDrawer {...props} />);
    fireEvent.change(screen.getByTestId("coverage-add-input"), { target: { value: "nvda" } });
    fireEvent.click(screen.getByTestId("coverage-add-btn"));
    await waitFor(() => expect(props.onAdd).toHaveBeenCalledWith("NVDA"));
  });

  test("remove calls onRemove with the entry id", () => {
    const props = baseProps();
    render(<CoverageDrawer {...props} />);
    fireEvent.click(screen.getByTestId("coverage-remove-e-AAPL"));
    expect(props.onRemove).toHaveBeenCalledWith("e-AAPL");
  });

  test("backdrop click and Escape both close", () => {
    const props = baseProps();
    render(<CoverageDrawer {...props} />);
    fireEvent.click(screen.getByTestId("coverage-backdrop"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });

  test("empty watchlist shows the add-first prompt", () => {
    render(<CoverageDrawer {...baseProps()} entries={[]} runs={[]} />);
    expect(screen.getByTestId("coverage-empty")).toBeInTheDocument();
  });

  test("renders nothing when closed", () => {
    const { container } = render(<CoverageDrawer {...baseProps()} open={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
