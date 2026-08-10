// Minimal EventSource replacement for demo mode. Replays a scripted sequence
// of named events per URL so the streaming cockpits (Equity Research, Morning
// Briefing, Earnings Update) animate a full run without a server. URLs with no
// registered script (e.g. the app-wide notifications stream) just open and stay
// quiet.

import { sleep } from "./clock";

export interface StreamFrame {
  event: string;
  data: unknown;
  delayMs?: number;
}

/** Returns the frames to replay for a URL, or null if this factory doesn't
 *  handle it. */
export type StreamFactory = (url: URL) => StreamFrame[] | null;

const factories: StreamFactory[] = [];

export function registerStream(factory: StreamFactory): void {
  factories.push(factory);
}

const CONNECTING = 0;
const OPEN = 1;
const CLOSED = 2;

type Listener = (ev: MessageEvent) => void;

export class DemoEventSource extends EventTarget {
  static readonly CONNECTING = CONNECTING;
  static readonly OPEN = OPEN;
  static readonly CLOSED = CLOSED;

  readonly CONNECTING = CONNECTING;
  readonly OPEN = OPEN;
  readonly CLOSED = CLOSED;

  readonly url: string;
  readonly withCredentials: boolean;
  readyState: number = CONNECTING;

  onopen: ((ev: Event) => void) | null = null;
  onmessage: Listener | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string | URL, init?: { withCredentials?: boolean }) {
    super();
    this.url = typeof url === "string" ? url : url.href;
    this.withCredentials = init?.withCredentials ?? false;
    void this.#run();
  }

  async #run(): Promise<void> {
    const parsed = new URL(this.url, window.location.origin);
    let frames: StreamFrame[] | null = null;
    for (const factory of factories) {
      frames = factory(parsed);
      if (frames) break;
    }

    // Yield so the caller can attach listeners before the "open" event.
    await sleep(0);
    if (this.readyState === CLOSED) return;
    this.readyState = OPEN;
    const openEv = new Event("open");
    this.onopen?.(openEv);
    this.dispatchEvent(openEv);

    if (!frames) return; // no script: stay open, emit nothing.

    for (const frame of frames) {
      if (this.readyState === CLOSED) return;
      await sleep(frame.delayMs ?? 280);
      if (this.readyState === CLOSED) return;
      const ev = new MessageEvent(frame.event, {
        data: JSON.stringify(frame.data),
      });
      if (frame.event === "message") this.onmessage?.(ev);
      this.dispatchEvent(ev);
    }
  }

  close(): void {
    this.readyState = CLOSED;
  }
}
