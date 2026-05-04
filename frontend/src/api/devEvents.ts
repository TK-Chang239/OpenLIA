import { fetchJson, ApiError } from "./client";

export interface DevEvent {
  seq: number;
  ts: string;
  category: string;
  message: string;
  payload: Record<string, unknown>;
}

/** Resolves to true when the server has ``OPENLIA_DEV_MODE`` set; false on 404. */
export async function isDevModeEnabled(): Promise<boolean> {
  try {
    await fetchJson<{ enabled: true }>("/api/dev/info");
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return false;
    return false;
  }
}

export async function listDevEvents(): Promise<DevEvent[]> {
  const r = await fetchJson<{ items: DevEvent[] }>("/api/dev/events");
  return r.items;
}

/** Open an EventSource on ``/api/dev/events/stream`` and call ``onEvent``
 *  for each ``dev.event`` SSE frame. Returns a close handle. */
export function streamDevEvents(onEvent: (e: DevEvent) => void): () => void {
  const es = new EventSource("/api/dev/events/stream");
  const handler = (msg: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(msg.data) as DevEvent);
    } catch {
      // ignore malformed frames
    }
  };
  es.addEventListener("dev.event", handler as EventListener);
  return () => {
    es.removeEventListener("dev.event", handler as EventListener);
    es.close();
  };
}
