import { describe, expect, it } from "vitest";

import type { EuEvent } from "../../../api/earnings-update";
import { deriveEuPhase } from "../feed/euPhase";

const ev = (type: EuEvent["type"], payload: Record<string, unknown> = {}): EuEvent => ({
  type,
  payload,
});

describe("deriveEuPhase", () => {
  it("starts in connect with RUN_STARTED and only connect active", () => {
    const p = deriveEuPhase([ev("run.started", { subject: "AAPL" })]);
    expect(p.phaseKey).toBe("connect");
    expect(p.monoCode).toBe("RUN_STARTED");
    expect(p.pips).toEqual({
      connect: "active",
      research: "pending",
      write: "pending",
      finalize: "pending",
    });
  });

  it("moves to research on a data tool call and uses args_summary as mono", () => {
    const p = deriveEuPhase([
      ev("run.started"),
      ev("tool.called", { tool_name: "get_earnings_calendar", args_summary: "AAPL Q2" }),
    ]);
    expect(p.phaseKey).toBe("research");
    expect(p.monoCode).toBe("AAPL Q2");
    expect(p.pips.connect).toBe("done");
    expect(p.pips.research).toBe("active");
  });

  it("falls back to the tool name when no args_summary", () => {
    const p = deriveEuPhase([ev("tool.called", { tool_name: "fetch_fundamentals" })]);
    expect(p.phaseKey).toBe("research");
    expect(p.monoCode).toBe("fetch_fundamentals");
  });

  it("moves to write on section.written and shows the section title", () => {
    const p = deriveEuPhase([
      ev("tool.called", { tool_name: "get_earnings_calendar" }),
      ev("section.written", { title: "Guidance" }),
    ]);
    expect(p.phaseKey).toBe("write");
    expect(p.monoCode).toBe("Guidance");
    expect(p.pips.research).toBe("done");
    expect(p.pips.write).toBe("active");
  });

  it("moves to finalize on set_cover and marks all prior phases done", () => {
    const p = deriveEuPhase([
      ev("section.written", { title: "Guidance" }),
      ev("tool.called", { tool_name: "set_cover" }),
    ]);
    expect(p.phaseKey).toBe("finalize");
    expect(p.monoCode).toBe("FINALIZING");
    expect(p.pips).toEqual({
      connect: "done",
      research: "done",
      write: "done",
      finalize: "active",
    });
  });

  it("never moves backwards once a later phase is reached", () => {
    const p = deriveEuPhase([
      ev("tool.called", { tool_name: "set_cover" }),
      ev("tool.called", { tool_name: "get_earnings_calendar" }),
    ]);
    expect(p.phaseKey).toBe("finalize");
  });

  it("handles a dict args_summary without throwing (real backend shape)", () => {
    const p = deriveEuPhase([
      ev("tool.called", {
        tool_name: "get_earnings_calendar",
        args_summary: { symbol: "AAPL", period: "Q2" },
      }),
    ]);
    expect(p.phaseKey).toBe("research");
    expect(p.monoCode).toContain("AAPL");
  });

  it("falls back to the tool name when args_summary is an empty dict", () => {
    const p = deriveEuPhase([
      ev("tool.called", { tool_name: "fetch_news", args_summary: {} }),
    ]);
    expect(p.phaseKey).toBe("research");
    expect(p.monoCode).toBe("fetch_news");
  });
});
