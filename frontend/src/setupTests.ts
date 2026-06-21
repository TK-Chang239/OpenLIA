import "@testing-library/jest-dom";
import { afterEach } from "vitest";
// Initialize i18next so components that call useTranslation() resolve
// against the real English bundle. Without this, every t() call returns
// the raw key (e.g. "nav.home"), which makes selectors that match the
// displayed label fail. The initial language defaults to "en" because
// localStorage is empty and jsdom's navigator.language is "en-US".
import "./i18n";

// jsdom + undici realm mismatch on AbortSignal.
//
// react-router's createClientSideRequest builds `new Request(url, {signal})`
// using the AbortSignal from a global AbortController. Under jsdom, the global
// AbortController/AbortSignal are jsdom's own implementations, but the global
// Request is Node's bundled-undici Request. undici validates
// `signal instanceof <its own AbortSignal>` and the jsdom signal fails that
// check, throwing an unhandled "Expected signal to be an instance of
// AbortSignal" rejection that fails the whole vitest run (SettingsShellBlocker
// and SettingsPage navigate during their tests). Node's native classes that
// undici accepts are not recoverable here (jsdom has already replaced the
// globals), so wrap the global Request so a foreign-realm signal is dropped
// before it reaches undici's validator. Tests never assert on signal-driven
// aborts, so dropping the signal is behavior-preserving for them; requests
// without a signal validate cleanly.
{
  const OriginalRequest = globalThis.Request;
  if (typeof OriginalRequest === "function") {
    class RealmSafeRequest extends OriginalRequest {
      constructor(input: RequestInfo | URL, init?: RequestInit) {
        if (init && "signal" in init) {
          const safeInit = { ...init };
          delete safeInit.signal;
          super(input, safeInit);
        } else {
          super(input, init);
        }
      }
    }
    (globalThis as { Request: typeof Request }).Request =
      RealmSafeRequest as typeof Request;
  }
}

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

// jsdom's File/Blob lacks the .text() async helper that browsers ship.
// Components that handle file uploads (V23TemplateUploadModal, etc.)
// rely on it; polyfill via FileReader so tests can pass File instances
// without each one mocking the prototype.
const _blobProto = globalThis.Blob?.prototype as
  | (Blob & { text?: () => Promise<string> })
  | undefined;
if (_blobProto && typeof _blobProto.text !== "function") {
  _blobProto.text = function text(this: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result ?? ""));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(this);
    });
  };
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
