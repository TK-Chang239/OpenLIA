// Route registry for the demo fetch shim. Each domain module under data/
// registers a handful of routes; the fetch shim (fetchRouter.ts) walks this
// list to answer /api requests from fake data.

export type Params = Record<string, string>;

export interface DemoRequest {
  method: string;
  url: URL;
  path: string;
  params: Params;
  /** Parsed JSON request body, when the caller sent one as a string. */
  body: unknown;
}

/** One SSE frame for a streamed response (used by the chat POST endpoint). */
export interface SseFrame {
  event?: string;
  data: unknown;
  delayMs?: number;
}

export type DemoResult =
  | { status?: number; json?: unknown }
  | { sse: SseFrame[] };

export type Handler = (req: DemoRequest) => DemoResult | Promise<DemoResult>;

export interface RouteDef {
  method: string;
  /** Express-style pattern, e.g. "/api/portfolio/value_series" or
   *  "/api/departments/equity-research/v3/runs/:id". */
  pattern: string;
  handler: Handler;
}

const routes: RouteDef[] = [];

/** Called at import time by each data module to register its routes. */
export function register(defs: RouteDef[]): void {
  routes.push(...defs);
}

export function getRoutes(): readonly RouteDef[] {
  return routes;
}

/** Convenience for handlers that return plain JSON. */
export function json(body: unknown, status = 200): DemoResult {
  return { status, json: body };
}

/** Convenience for a not-found style response. */
export function notFound(detail = "demo_not_found"): DemoResult {
  return { status: 404, json: { detail } };
}

const PARAM = /:[A-Za-z0-9_]+/g;

/** Match a pathname against a pattern, returning captured params or null. */
export function matchPattern(pattern: string, pathname: string): Params | null {
  const names: string[] = [];
  const source =
    "^" +
    pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(PARAM, (m) => {
      names.push(m.slice(1));
      return "([^/]+)";
    }) +
    "/?$";
  const re = new RegExp(source);
  const m = re.exec(pathname);
  if (!m) return null;
  const params: Params = {};
  names.forEach((name, i) => {
    params[name] = decodeURIComponent(m[i + 1]);
  });
  return params;
}
