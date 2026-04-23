import { describe, expect, it, beforeEach, vi } from "vitest";
import { createSession, listSessions, listMessages, deleteSession, patchSession } from "../chat";
import { saveToRepo, unsaveFromRepo, listRepoItems } from "../repo";
import { downloadUrlForReport, downloadUrlForAttachment } from "../files";

const UUID1 = "00000000-0000-4000-8000-000000000001";
const UUID2 = "00000000-0000-4000-8000-000000000002";

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

describe("chat api", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("listSessions fetches /api/chat/sessions", async () => {
    mockFetch({ items: [{ id: UUID1, department: "secretary", title: "x", is_pinned: false, is_archived: false, created_at: "2026-04-01T00:00:00Z" }] });
    const r = await listSessions();
    expect(r.items[0].department).toBe("secretary");
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/chat/sessions");
  });

  it("listSessions with includeArchived adds query param", async () => {
    mockFetch({ items: [] });
    await listSessions(true);
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("include_archived=true");
  });

  it("createSession POSTs to /api/chat/sessions", async () => {
    mockFetch({ id: UUID2, department: "secretary", title: "y", is_pinned: false, is_archived: false, created_at: "2026-04-01T00:00:00Z" });
    const r = await createSession({ department: "secretary", title: "y" });
    expect(r.id).toBe(UUID2);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("POST");
  });

  it("patchSession sends PATCH", async () => {
    mockFetch({ ok: true });
    await patchSession(UUID1, { title: "renamed" });
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`/api/chat/sessions/${UUID1}`);
    expect(init.method).toBe("PATCH");
  });

  it("deleteSession sends DELETE", async () => {
    mockFetch({}, 204);
    await deleteSession(UUID1);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("DELETE");
  });

  it("listMessages fetches session messages", async () => {
    mockFetch({ items: [{ id: UUID1, role: "user", content: "hi", tool_calls: null, model_ref: null, token_usage: null, created_at: "2026-04-01T00:00:00Z" }] });
    const r = await listMessages(UUID1);
    expect(r.items[0].role).toBe("user");
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`/api/chat/sessions/${UUID1}/messages`);
  });
});

describe("repo api", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("saveToRepo POSTs report_id", async () => {
    mockFetch({ id: UUID1, report_id: UUID2, created_at: "2026-04-01T00:00:00Z" });
    const r = await saveToRepo(UUID2);
    expect(r.report_id).toBe(UUID2);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("POST");
  });

  it("unsaveFromRepo sends DELETE with query param", async () => {
    mockFetch({}, 204);
    await unsaveFromRepo(UUID2);
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`/api/repo/items?report_id=${UUID2}`);
    expect(init.method).toBe("DELETE");
  });

  it("listRepoItems returns list", async () => {
    mockFetch({ items: [] });
    const r = await listRepoItems();
    expect(r.items).toEqual([]);
  });
});

describe("files helpers", () => {
  it("downloadUrlForReport returns correct URL", () => {
    expect(downloadUrlForReport(UUID1)).toBe(`/api/reports/${UUID1}/download`);
  });

  it("downloadUrlForAttachment returns correct URL", () => {
    expect(downloadUrlForAttachment(UUID2)).toBe(`/api/chat/attachments/${UUID2}/download`);
  });
});
