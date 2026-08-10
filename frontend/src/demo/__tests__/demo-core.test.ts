import { describe, it, expect } from "vitest";
import { demoFetch } from "../fetchRouter";
import { DemoEventSource, registerStream } from "../DemoEventSource";
// Side-effect imports register the bootstrap + markets routes.
import "../data/bootstrap";
import "../data/markets";

describe("demo fetch router", () => {
  it("reports the setup wizard as completed", async () => {
    const res = await demoFetch("/api/setup/status");
    expect(res.status).toBe(200);
    const body = (await res.json()) as { wizard_completed: boolean };
    expect(body.wizard_completed).toBe(true);
  });

  it("returns 404 for the auth session (drops app into personal mode)", async () => {
    const res = await demoFetch("/api/auth/session");
    expect(res.status).toBe(404);
  });

  it("marks every department active in dept-health", async () => {
    const res = await demoFetch("/api/dept-health");
    const body = (await res.json()) as Array<{ status: string }>;
    expect(body.length).toBeGreaterThan(0);
    expect(body.every((d) => d.status === "active")).toBe(true);
  });

  it("serves market indices for the Home ticker strip", async () => {
    const res = await demoFetch("/api/markets/indices");
    const body = (await res.json()) as { indices: unknown[] };
    expect(body.indices.length).toBeGreaterThan(0);
  });

  it("404s unmapped api routes", async () => {
    const res = await demoFetch("/api/does/not/exist");
    expect(res.status).toBe(404);
  });
});

describe("DemoEventSource", () => {
  it("replays a registered stream script in order", async () => {
    registerStream((url) =>
      url.pathname === "/api/_test/stream"
        ? [
            { event: "run.started", data: { phase: "start" }, delayMs: 1 },
            { event: "run.completed", data: { ok: true }, delayMs: 1 },
          ]
        : null,
    );

    const es = new DemoEventSource("/api/_test/stream");
    const seen: string[] = [];
    await new Promise<void>((resolve) => {
      es.addEventListener("run.started", () => seen.push("started"));
      es.addEventListener("run.completed", (ev) => {
        const data = JSON.parse((ev as MessageEvent).data) as { ok: boolean };
        seen.push(data.ok ? "completed" : "failed");
        resolve();
      });
    });
    expect(seen).toEqual(["started", "completed"]);
  });
});
