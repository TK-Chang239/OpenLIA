import { describe, expect, test } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { V3Event } from "../../../api/equity-research-v3";
import { V3ActivityFeed, summarizePayload } from "../V3ActivityFeed";

function ev(type: V3Event["type"], payload: Record<string, unknown>): V3Event {
  return { type, payload } as V3Event;
}

describe("V3ActivityFeed", () => {
  test("shows a starting row when there are no events", () => {
    render(<V3ActivityFeed events={[]} />);
    expect(screen.getByTestId("er-v3-activity-feed")).toHaveTextContent("Starting run");
  });

  test("renders the most recent events (newest last) and caps the collapsed view", () => {
    const events: V3Event[] = Array.from({ length: 9 }, (_, i) =>
      ev("section.written", { section_id: `s${i}`, char_count: 100 + i }),
    );
    render(<V3ActivityFeed events={events} />);
    const rows = screen.getAllByTestId("er-v3-activity-row");
    expect(rows.length).toBe(6); // collapsed cap
    expect(screen.getByText(/s8/)).toBeInTheDocument();
    expect(screen.queryByText(/\bs0\b/)).toBeNull();
  });

  test("'Show all activity' expands to the full history", () => {
    const events: V3Event[] = Array.from({ length: 9 }, (_, i) =>
      ev("section.written", { section_id: `s${i}`, char_count: 100 + i }),
    );
    render(<V3ActivityFeed events={events} />);
    fireEvent.click(screen.getByTestId("er-v3-activity-toggle"));
    expect(screen.getAllByTestId("er-v3-activity-row").length).toBe(9);
    expect(screen.getByText(/\bs0\b/)).toBeInTheDocument();
  });
});

describe("summarizePayload", () => {
  test("run.started shows subject and model", () => {
    expect(summarizePayload(ev("run.started", { subject: "AAPL", model: "claude" }))).toBe(
      "AAPL — claude",
    );
  });
  test("tool.completed includes ok status and source_id when present", () => {
    expect(
      summarizePayload(ev("tool.completed", { turn: 2, tool_name: "web_search", ok: true, source_id: "web_1" })),
    ).toBe("turn 2 ← web_search (ok) web_1");
  });
  test("tool.completed marks errors", () => {
    expect(
      summarizePayload(ev("tool.completed", { turn: 1, tool_name: "calc", ok: false })),
    ).toBe("turn 1 ← calc (error)");
  });
  test("run.completed summarizes counts", () => {
    expect(
      summarizePayload(ev("run.completed", { section_count: 6, chart_count: 1, citation_count: 5 })),
    ).toBe("6 sections · 1 charts · 5 citations");
  });
});
