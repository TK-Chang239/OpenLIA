import { describe, expect, it, beforeEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useChatStream } from "../useChatStream";

interface CapturedRequest {
  url: string;
  method: string;
  contentType: string;
  body: BodyInit | null | undefined;
}

function makeCapturingFetch(): {
  fetchImpl: typeof fetch;
  captured: CapturedRequest[];
} {
  const captured: CapturedRequest[] = [];
  const fetchImpl: typeof fetch = (input, init) => {
    captured.push({
      url: typeof input === "string" ? input : (input as URL).toString(),
      method: init?.method ?? "GET",
      contentType: ((init?.headers as Record<string, string>) ?? {})[
        "Content-Type"
      ] ?? "",
      body: init?.body,
    });
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const enc = new TextEncoder();
        controller.enqueue(
          enc.encode(`event: chat.done\ndata: ${JSON.stringify({})}\n\n`),
        );
        controller.close();
      },
    });
    return Promise.resolve(
      new Response(stream as unknown as BodyInit, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }) as Response,
    );
  };
  return { fetchImpl, captured };
}

const SESSION = "s-1";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useChatStream attachments", () => {
  it("send(text) without files keeps the JSON payload shape", async () => {
    const { fetchImpl, captured } = makeCapturingFetch();
    const { result } = renderHook(() =>
      useChatStream({
        sessionId: SESSION,
        fetchImpl,
        streamUrl: "/api/departments/secretary/chat",
      }),
    );
    act(() => result.current.send("hello"));
    await new Promise((r) => setTimeout(r, 5));

    expect(captured).toHaveLength(1);
    expect(captured[0].method).toBe("POST");
    expect(captured[0].contentType).toBe("application/json");
    expect(captured[0].body).toBe(
      JSON.stringify({ message: "hello" }),
    );
  });

  it("send(text, files) builds a multipart/form-data body", async () => {
    const { fetchImpl, captured } = makeCapturingFetch();
    const { result } = renderHook(() =>
      useChatStream({
        sessionId: SESSION,
        fetchImpl,
        streamUrl: "/api/departments/secretary/chat",
      }),
    );

    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    act(() => result.current.send("read this", [file]));
    await new Promise((r) => setTimeout(r, 5));

    expect(captured).toHaveLength(1);
    expect(captured[0].body).toBeInstanceOf(FormData);

    const form = captured[0].body as FormData;
    expect(form.get("message")).toBe("read this");
    const files = form.getAll("files");
    expect(files).toHaveLength(1);
    expect((files[0] as File).name).toBe("notes.txt");
    // Browser sets multipart Content-Type with boundary automatically when
    // the body is a FormData instance — we must NOT set it ourselves.
    expect(captured[0].contentType).toBe("");
  });

  it("send(text, files) carries multiple files in the same field", async () => {
    const { fetchImpl, captured } = makeCapturingFetch();
    const { result } = renderHook(() =>
      useChatStream({
        sessionId: SESSION,
        fetchImpl,
        streamUrl: "/api/departments/secretary/chat",
      }),
    );

    const a = new File(["a"], "a.txt", { type: "text/plain" });
    const b = new File(["b"], "b.txt", { type: "text/plain" });
    act(() => result.current.send("two", [a, b]));
    await new Promise((r) => setTimeout(r, 5));

    const form = captured[0].body as FormData;
    expect(form.getAll("files")).toHaveLength(2);
    expect((form.getAll("files")[0] as File).name).toBe("a.txt");
    expect((form.getAll("files")[1] as File).name).toBe("b.txt");
  });

  it("send(text, []) treats empty array the same as no files (JSON path)", async () => {
    const { fetchImpl, captured } = makeCapturingFetch();
    const { result } = renderHook(() =>
      useChatStream({
        sessionId: SESSION,
        fetchImpl,
        streamUrl: "/api/departments/secretary/chat",
      }),
    );
    act(() => result.current.send("hi", []));
    await new Promise((r) => setTimeout(r, 5));

    expect(captured[0].contentType).toBe("application/json");
    expect(captured[0].body).toBe(JSON.stringify({ message: "hi" }));
  });

  it("send(text, files) merges bodyExtras (e.g. session_id) into the FormData", async () => {
    const { fetchImpl, captured } = makeCapturingFetch();
    const { result } = renderHook(() =>
      useChatStream({
        sessionId: SESSION,
        fetchImpl,
        streamUrl: "/api/departments/secretary/chat",
        bodyExtras: { session_id: "s-99" },
      }),
    );
    const file = new File(["x"], "x.txt", { type: "text/plain" });
    act(() => result.current.send("look", [file]));
    await new Promise((r) => setTimeout(r, 5));

    const form = captured[0].body as FormData;
    expect(form.get("message")).toBe("look");
    expect(form.get("session_id")).toBe("s-99");
  });
});
