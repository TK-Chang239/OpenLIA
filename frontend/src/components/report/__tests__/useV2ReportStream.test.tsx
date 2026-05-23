import { describe, expect, it } from "vitest";

import { v2Reducer, type V2StreamState } from "../useV2ReportStream";

const INITIAL: V2StreamState = {
  status: "idle",
  currentStage: null,
  completedStages: [],
  runId: null,
  pausedOutput: null,
  pausedRound: null,
  report: null,
  failedStage: null,
  failedReason: null,
};

describe("v2Reducer", () => {
  it("START moves into starting state and clears prior payload", () => {
    const seeded: V2StreamState = {
      ...INITIAL,
      status: "failed",
      failedReason: "old",
    };
    const next = v2Reducer(seeded, { kind: "START" });
    expect(next.status).toBe("starting");
    expect(next.failedReason).toBeNull();
  });

  it("stage.started moves to running and records currentStage", () => {
    const next = v2Reducer(
      { ...INITIAL, status: "starting" },
      { kind: "EVENT", event: "stage.started", data: { stage: "clarify" } },
    );
    expect(next.status).toBe("running");
    expect(next.currentStage).toBe("clarify");
  });

  it("stage.completed appends to completedStages without duplicates", () => {
    let state = v2Reducer(INITIAL, {
      kind: "EVENT",
      event: "stage.completed",
      data: { stage: "clarify" },
    });
    state = v2Reducer(state, {
      kind: "EVENT",
      event: "stage.completed",
      data: { stage: "clarify" },
    });
    expect(state.completedStages).toEqual(["clarify"]);
  });

  it("clarifier.pause captures the output and round, status = paused", () => {
    const output = {
      questions: [],
      blocking_warnings: [
        {
          capability_id: "extra_passes",
          detected_phrase: "devil's advocate",
          user_message: "msg",
          available_actions: [
            "proceed_without",
            "cancel_and_edit",
            "clarify",
          ],
        },
      ],
      notices: [],
      detected_intents: ["extra_passes"],
    };
    const next = v2Reducer(INITIAL, {
      kind: "EVENT",
      event: "clarifier.pause",
      data: { run_id: "r1", round: 1, output },
    });
    expect(next.status).toBe("paused");
    expect(next.pausedOutput).toEqual(output);
    expect(next.pausedRound).toBe(1);
    expect(next.runId).toBe("r1");
  });

  it("next stage.started after pause clears pausedOutput", () => {
    const paused: V2StreamState = {
      ...INITIAL,
      status: "paused",
      pausedOutput: { blocking_warnings: [] } as never,
      pausedRound: 1,
    };
    const next = v2Reducer(paused, {
      kind: "EVENT",
      event: "stage.started",
      data: { stage: "research_plan" },
    });
    expect(next.status).toBe("running");
    expect(next.pausedOutput).toBeNull();
    expect(next.pausedRound).toBeNull();
  });

  it("completed captures structured report and sets status to complete", () => {
    const fakeReport = {
      engine_version: "2.2",
      generated_at: "2026-05-22T19:30:00Z",
      template_id: "stock_research_v2",
      template_name: "Stock Research (v2)",
      cover: { title: "AAPL", ticker: "AAPL" },
      sections: [{ id: "intro", name: "Intro", blocks: [] }],
      citations: [],
      run_summary: { engine_version: "2.2" },
    };
    const next = v2Reducer(INITIAL, {
      kind: "EVENT",
      event: "completed",
      data: { run_id: "r1", report: fakeReport },
    });
    expect(next.status).toBe("complete");
    expect(next.report).toEqual(fakeReport);
    expect(next.runId).toBe("r1");
  });

  it("failed captures stage + reason and sets status to failed", () => {
    const next = v2Reducer(INITIAL, {
      kind: "EVENT",
      event: "failed",
      data: { run_id: "r1", stage: "research_plan", reason: "boom" },
    });
    expect(next.status).toBe("failed");
    expect(next.failedStage).toBe("research_plan");
    expect(next.failedReason).toBe("boom");
  });

  it("STOP transitions running → failed but does not overwrite a final state", () => {
    const running: V2StreamState = { ...INITIAL, status: "running" };
    expect(v2Reducer(running, { kind: "STOP" }).status).toBe("failed");

    const complete: V2StreamState = { ...INITIAL, status: "complete" };
    expect(v2Reducer(complete, { kind: "STOP" })).toEqual(complete);
  });

  it("RESUME preserves runId / pausedOutput so the modal can fade cleanly", () => {
    const paused: V2StreamState = {
      ...INITIAL,
      status: "paused",
      runId: "r1",
      pausedRound: 1,
      pausedOutput: { blocking_warnings: [] } as never,
    };
    const next = v2Reducer(paused, { kind: "RESUME" });
    expect(next.status).toBe("starting");
    expect(next.runId).toBe("r1");
    expect(next.pausedOutput).not.toBeNull();
  });
});
