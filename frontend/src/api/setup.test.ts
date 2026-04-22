import { describe, it, expect, vi, beforeEach } from "vitest";
import * as setup from "./setup";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("api/setup", () => {
  it("getStatus returns parsed body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          mode: "personal",
          wizard_completed: false,
          current_step: "mode",
          completed_steps: [],
          env_overrides: {},
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const status = await setup.getStatus();
    expect(status.mode).toBe("personal");
    expect(status.wizard_completed).toBe(false);
  });

  it("setMode posts to /api/setup/mode", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ mode: "company" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await setup.setMode("company");
    expect(spy).toHaveBeenCalledWith(
      "/api/setup/mode",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("finish returns redirect target", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ redirect: "/login", mode: "company" }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await setup.finish();
    expect(result.redirect).toBe("/login");
  });
});
