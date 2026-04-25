export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(status: number, message: string, body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export interface FetchOptions extends Omit<RequestInit, "body"> {
  json?: unknown;
}

function resolveUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const base =
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
  if (!base) return path;
  const trimmedBase = base.replace(/\/+$/, "");
  const trimmedPath = path.startsWith("/") ? path : `/${path}`;
  return `${trimmedBase}${trimmedPath}`;
}

export async function fetchJson<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { json, headers, ...rest } = options;

  const init: RequestInit = {
    credentials: "include",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };

  if (json !== undefined) {
    init.body = JSON.stringify(json);
  }

  const url = resolveUrl(path);

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    const message = err instanceof Error ? err.message : "network error";
    throw new ApiError(0, message);
  }

  if (response.status === 204) {
    return null as T;
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  const parsedBody = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `HTTP ${response.status} on ${url}`,
      parsedBody,
    );
  }

  return parsedBody as T;
}
