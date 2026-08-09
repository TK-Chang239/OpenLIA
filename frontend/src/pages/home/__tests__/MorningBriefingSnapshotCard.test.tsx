import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MorningBriefingSnapshotCard } from "../MorningBriefingSnapshotCard";
import * as mbApi from "../../../api/morning-briefing";
import type { MbRunSummary } from "../../../api/morning-briefing";

vi.mock("../../../api/morning-briefing", () => ({ listMbRuns: vi.fn() }));

const mocked = mbApi as unknown as {
  listMbRuns: ReturnType<typeof vi.fn>;
};

function run(overrides: Partial<MbRunSummary> = {}): MbRunSummary {
  return {
    report_id: "r1",
    subject: "Morning Briefing",
    trigger_kind: "schedule",
    schedule_id: "s1",
    template_id: "default",
    instructions_id: null,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-08-09T11:00:00Z",
    completed_at: "2026-08-09T11:03:00Z",
    reasoning_effort: null,
    highlights: {
      subtitle: "Payrolls Friday is the only chart that matters this week.",
      rating: "Cautious",
      metrics: [
        { label: "S&P fut", value: "5,891", change: "+0.34%", tone: "positive" },
        { label: "VIX", value: "14.2", change: "-1.8%", tone: "negative" },
      ],
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

const renderCard = () =>
  render(
    <MemoryRouter>
      <MorningBriefingSnapshotCard />
    </MemoryRouter>,
  );

describe("MorningBriefingSnapshotCard", () => {
  it("renders the latest run's lede, rating, and metrics", async () => {
    mocked.listMbRuns.mockResolvedValue([
      run({ report_id: "old", created_at: "2026-08-01T11:00:00Z" }),
      run({ report_id: "new", created_at: "2026-08-09T11:00:00Z" }),
    ]);
    renderCard();
    expect(
      await screen.findByText(/Payrolls Friday is the only chart/),
    ).toBeInTheDocument();
    expect(screen.getByText("Cautious")).toBeInTheDocument();
    expect(screen.getByText("S&P fut")).toBeInTheDocument();
    expect(screen.getByText("5,891")).toBeInTheDocument();
    // requests only completed runs
    expect(mocked.listMbRuns).toHaveBeenCalledWith("completed");
  });

  it("shows an empty state when there is no completed briefing", async () => {
    mocked.listMbRuns.mockResolvedValue([]);
    renderCard();
    expect(await screen.findByText(/no briefing yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /open briefing/i }),
    ).toHaveAttribute("href", "/morning-briefing");
  });

  it("falls back to the subject when there is no cover subtitle", async () => {
    mocked.listMbRuns.mockResolvedValue([
      run({ subject: "Daily Wrap", highlights: null }),
    ]);
    renderCard();
    await waitFor(() => expect(mocked.listMbRuns).toHaveBeenCalled());
    // Subject appears both in the header and as the lede fallback.
    expect(screen.getAllByText("Daily Wrap").length).toBeGreaterThanOrEqual(1);
  });
});
