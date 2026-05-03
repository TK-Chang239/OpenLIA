import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useChatStream } from "../useChatStream";

interface PushHandle {
  emit: (type: string, data: unknown) => void;
  closeServer: () => void;
}

function makeMockFetch() {
  const handles: PushHandle[] = [];
  const fetchImpl: typeof fetch = (_input, init) => {
    let pushed: (chunk: Uint8Array) => void = () => {};
    let close: () => void = () => {};
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        pushed = (chunk: Uint8Array) => controller.enqueue(chunk);
        close = () => {
          try {
            controller.close();
          } catch {}
        };
      },
    });
    const enc = new TextEncoder();
    const handle: PushHandle = {
      emit: (type, data) => {
        const frame = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
        try {
          pushed(enc.encode(frame));
        } catch {}
      },
      closeServer: () => close(),
    };
    const signal = init?.signal as AbortSignal | undefined;
    if (signal) {
      signal.addEventListener("abort", () => close());
    }
    handles.push(handle);
    return Promise.resolve(
      new Response(stream as unknown as BodyInit, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }) as Response,
    );
  };
  return { fetchImpl, handles };
}

const SESSION = "00000000-0000-4000-8000-000000000099";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useChatStream — chat.guardrail", () => {
  it("replaces the assistant message body when action='replaced'", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );

    act(() => result.current.send("say something bad"));
    await waitFor(() => expect(handles.length).toBe(1));

    act(() => handles[0].emit("chat.start", {}));
    await waitFor(() => expect(result.current.state.status).toBe("thinking"));

    act(() => handles[0].emit("chat.token", { text: "bad text" }));
    await waitFor(() => expect(result.current.state.message).toBe("bad text"));

    act(() =>
      handles[0].emit("chat.guardrail", {
        category: "harmful_content",
        action: "replaced",
        replacement: "I don't share that kind of information.",
      }),
    );
    await waitFor(() =>
      expect(result.current.state.message).toBe(
        "I don't share that kind of information.",
      ),
    );

    expect(result.current.state.chunks).toEqual([
      { type: "text", text: "I don't share that kind of information." },
    ]);

    act(() => handles[0].emit("chat.done", {}));
    await waitFor(() => expect(result.current.state.status).toBe("done"));
  });

  it("appends a flag chip when action='warned'", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );

    act(() => result.current.send("some question"));
    await waitFor(() => expect(handles.length).toBe(1));

    act(() => handles[0].emit("chat.start", {}));
    await waitFor(() => expect(result.current.state.status).toBe("thinking"));

    act(() => handles[0].emit("chat.token", { text: "some text" }));
    await waitFor(() => expect(result.current.state.message).toBe("some text"));

    act(() =>
      handles[0].emit("chat.guardrail", {
        category: "advice_phrasing",
        action: "warned",
        chip_text: "Flagged: phrasing review suggested",
      }),
    );
    await waitFor(() =>
      expect(result.current.state.flagChips).toEqual([
        { category: "advice_phrasing", text: "Flagged: phrasing review suggested" },
      ]),
    );

    // Message text must be unchanged
    expect(result.current.state.message).toBe("some text");

    act(() => handles[0].emit("chat.done", {}));
    await waitFor(() => expect(result.current.state.status).toBe("done"));
  });
});
