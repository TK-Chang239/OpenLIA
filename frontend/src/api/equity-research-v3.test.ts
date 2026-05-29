import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { startV3RunAsync, type V3StartPayload } from "./equity-research-v3";

const BASE_PAYLOAD: V3StartPayload = {
  subject: "RKLB.US",
  language: "en",
  length: "normal",
  template_id: "initiation_default",
  provider_kind: "anthropic",
  model: "claude-sonnet-4-6",
  reasoning_effort: null,
};

describe("startV3RunAsync", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  function mockOk() {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ report_id: "r1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = spy as unknown as typeof fetch;
    return spy;
  }

  it("sends JSON when there are no files", async () => {
    const spy = mockOk();
    const res = await startV3RunAsync(BASE_PAYLOAD);
    expect(res.report_id).toBe("r1");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(typeof init.body).toBe("string");
    expect(JSON.parse(init.body as string).subject).toBe("RKLB.US");
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("sends multipart FormData when files are attached", async () => {
    const spy = mockOk();
    const file = new File([new Uint8Array([1, 2, 3])], "10k.pdf", {
      type: "application/pdf",
    });
    const res = await startV3RunAsync(BASE_PAYLOAD, [file]);
    expect(res.report_id).toBe("r1");

    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    // No application/json content-type — the browser sets the multipart boundary.
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();

    const fd = init.body as FormData;
    expect(fd.get("subject")).toBe("RKLB.US");
    expect(fd.get("provider_kind")).toBe("anthropic");
    const files = fd.getAll("files");
    expect(files).toHaveLength(1);
    expect((files[0] as File).name).toBe("10k.pdf");
  });

  it("surfaces a validation-error envelope from a multipart 400", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: { errors: [{ filename: "big.bin", reason: "file_too_large" }] },
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    );
    global.fetch = spy as unknown as typeof fetch;
    const file = new File([new Uint8Array([1])], "big.bin", { type: "application/pdf" });
    await expect(startV3RunAsync(BASE_PAYLOAD, [file])).rejects.toThrow(
      /big\.bin: file_too_large/,
    );
  });
});
