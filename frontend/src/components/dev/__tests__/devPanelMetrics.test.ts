import { describe, it, expect } from "vitest";

import type { DevEvent } from "../../../api/devEvents";
import { computeCostMetrics } from "../devPanelMetrics";

function makeEvent(
  seq: number,
  category: string,
  payload: Record<string, unknown>,
): DevEvent {
  return {
    seq,
    ts: "2026-05-15T00:00:00.000Z",
    category,
    message: category,
    payload,
  };
}

describe("computeCostMetrics", () => {
  it("returns all zeros for an empty event list", () => {
    const m = computeCostMetrics([]);
    expect(m.reportCount).toBe(0);
    expect(m.searchCount).toBe(0);
    expect(m.searchesPerReport).toBe(0);
    expect(m.rescueRate).toBe(0);
    expect(m.doubleBillEstimate).toBe(0);
  });

  it("counts configured tool_call web_search events as searches", () => {
    const events: DevEvent[] = [
      makeEvent(1, "report.request", { report_id: "r1" }),
      makeEvent(2, "report.tool_call", {
        report_id: "r1",
        tool_name: "web_search",
      }),
      makeEvent(3, "report.tool_call", {
        report_id: "r1",
        tool_name: "web_search",
      }),
      makeEvent(4, "report.complete", { report_id: "r1" }),
    ];
    const m = computeCostMetrics(events);
    expect(m.reportCount).toBe(1);
    expect(m.searchCount).toBe(2);
    expect(m.searchesPerReport).toBe(2);
    expect(m.rescueRate).toBe(0);
  });

  it("treats web_search.rescue as a search and bumps rescueRate", () => {
    const events: DevEvent[] = [
      makeEvent(1, "report.request", { report_id: "r1" }),
      makeEvent(2, "web_search.rescue", { report_id: "r1" }),
    ];
    const m = computeCostMetrics(events);
    expect(m.reportCount).toBe(1);
    expect(m.searchCount).toBe(1);
    expect(m.rescueRate).toBe(1);
  });

  it("computes doubleBillEstimate as fraction of reports with both native and configured searches", () => {
    const events: DevEvent[] = [
      // Report 1 — has both native invoked AND configured tool_call web_search
      makeEvent(1, "report.request", { report_id: "r1" }),
      makeEvent(2, "report.web_search.invoked", { report_id: "r1" }),
      makeEvent(3, "report.tool_call", {
        report_id: "r1",
        tool_name: "web_search",
      }),
      // Report 2 — only configured tool_call web_search (single variety)
      makeEvent(4, "report.request", { report_id: "r2" }),
      makeEvent(5, "report.tool_call", {
        report_id: "r2",
        tool_name: "web_search",
      }),
    ];
    const m = computeCostMetrics(events);
    expect(m.reportCount).toBe(2);
    expect(m.doubleBillEstimate).toBe(0.5);
  });

  it("ignores events without a report_id", () => {
    const events: DevEvent[] = [
      makeEvent(1, "report.tool_call", { tool_name: "web_search" }),
      makeEvent(2, "web_search.rescue", {}),
    ];
    const m = computeCostMetrics(events);
    expect(m.reportCount).toBe(0);
    expect(m.searchCount).toBe(0);
    expect(m.searchesPerReport).toBe(0);
    expect(m.rescueRate).toBe(0);
    expect(m.doubleBillEstimate).toBe(0);
  });

  it("recognizes the backend's `tool` payload key (alias of tool_name)", () => {
    const events: DevEvent[] = [
      makeEvent(1, "report.request", { report_id: "r1" }),
      makeEvent(2, "report.tool_call", { report_id: "r1", tool: "web_search" }),
      makeEvent(3, "report.tool_call", { report_id: "r1", tool: "web_search" }),
    ];
    const m = computeCostMetrics(events);
    expect(m.searchCount).toBe(2);
  });

  it("does not count non-web_search tool_calls as searches", () => {
    const events: DevEvent[] = [
      makeEvent(1, "report.request", { report_id: "r1" }),
      makeEvent(2, "report.tool_call", {
        report_id: "r1",
        tool_name: "get_quote",
      }),
      makeEvent(3, "report.tool_call", {
        report_id: "r1",
        tool_name: "read_payload",
      }),
    ];
    const m = computeCostMetrics(events);
    expect(m.reportCount).toBe(1);
    expect(m.searchCount).toBe(0);
    expect(m.searchesPerReport).toBe(0);
  });
});
