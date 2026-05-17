import "@testing-library/jest-dom";
import { afterEach } from "vitest";

// jsdom does not implement EventSource. Several components (notifications
// stream, report stream) construct one on mount, which crashes any test that
// renders them without a per-test mock. Provide a no-op stub so those tests
// can render without explicit EventSource handling; tests that care about
// EventSource behavior still install their own mock and override this.
if (typeof (globalThis as { EventSource?: unknown }).EventSource === "undefined") {
  class NoopEventSource {
    url: string;
    constructor(url: string) {
      this.url = url;
    }
    addEventListener() {}
    removeEventListener() {}
    close() {}
    onmessage: ((e: MessageEvent) => void) | null = null;
    onerror: ((e: Event) => void) | null = null;
    onopen: ((e: Event) => void) | null = null;
  }
  (globalThis as { EventSource?: unknown }).EventSource = NoopEventSource;
}

// Wizard step components persist non-secret form fields to sessionStorage
// so back/forward navigation does not lose user input. Tests render those
// components multiple times in the same process — clear sessionStorage
// between tests so persisted state from one test does not leak into the
// next.
afterEach(() => {
  try {
    sessionStorage.clear();
  } catch {
    /* ignore environments without sessionStorage */
  }
});
