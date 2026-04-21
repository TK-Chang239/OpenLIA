import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getUnread, markRead } from "./notifications";

describe("notifications api", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("getUnread returns total + by_department", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          total: 3,
          by_department: { morning_briefing: 2, earnings_update: 1 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const resp = await getUnread();
    expect(resp.total).toBe(3);
    expect(resp.by_department.morning_briefing).toBe(2);
  });

  it("markRead POSTs the department", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await markRead("morning_briefing");

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/notifications/read");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      department: "morning_briefing",
    });
  });
});
