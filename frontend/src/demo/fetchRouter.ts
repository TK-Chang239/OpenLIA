// Demo fetch shim. Replaces globalThis.fetch when VITE_DEMO_MODE is set.
// Same-origin /api (and /notifications) requests are answered from the route
// registry; everything else falls through to the real fetch so static assets
// still load.

import {
  getRoutes,
  matchPattern,
  type DemoResult,
  type SseFrame,
} from "./registry";
import { sleep } from "./clock";

let originalFetch: typeof fetch = fetch;

export function setOriginalFetch(fn: typeof fetch): void {
  originalFetch = fn;
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  const m =
    init?.method ?? (input instanceof Request ? input.method : "GET");
  return m.toUpperCase();
}

function readBody(input: RequestInfo | URL, init?: RequestInit): unknown {
  const raw = init?.body ?? (input instanceof Request ? undefined : undefined);
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  }
  return undefined;
}

const encoder = new TextEncoder();

function sseStream(frames: SseFrame[]): ReadableStream<Uint8Array> {
  let i = 0;
  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      if (i >= frames.length) {
        controller.close();
        return;
      }
      const frame = frames[i++];
      if (frame.delayMs) await sleep(frame.delayMs);
      let chunk = "";
      if (frame.event) chunk += `event: ${frame.event}\n`;
      chunk += `data: ${JSON.stringify(frame.data)}\n\n`;
      controller.enqueue(encoder.encode(chunk));
    },
  });
}

function toResponse(result: DemoResult): Response {
  if ("sse" in result) {
    return new Response(sseStream(result.sse), {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  }
  const status = result.status ?? 200;
  if (status === 204 || result.json === undefined) {
    return new Response(null, { status });
  }
  return new Response(JSON.stringify(result.json), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function isDemoPath(pathname: string): boolean {
  return pathname.startsWith("/api") || pathname.startsWith("/notifications");
}

export const demoFetch: typeof fetch = async (input, init) => {
  const url = new URL(requestUrl(input), window.location.origin);
  const method = requestMethod(input, init);
  const pathname = url.pathname;

  for (const route of getRoutes()) {
    if (route.method.toUpperCase() !== method) continue;
    const params = matchPattern(route.pattern, pathname);
    if (!params) continue;
    const body = readBody(input, init);
    const result = await route.handler({ method, url, path: pathname, params, body });
    return toResponse(result);
  }

  if (isDemoPath(pathname)) {
    // Unmapped API route: surface it in the console during development, and
    // return an empty 404 so callers hit their existing error/empty paths.
    if (import.meta.env.DEV) {
      console.debug(`[demo] no route for ${method} ${pathname}`);
    }
    return new Response(JSON.stringify({ detail: "demo_no_route" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  return originalFetch(input, init);
};
