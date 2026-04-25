/**
 * Shared `fetch` wrapper used by every typed API client. Returns parsed JSON or
 * throws `ApiError` with the FastAPI envelope `{ detail: { code, message } }`.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = body.detail ?? {};
    const code: string =
      typeof detail === 'string' ? detail : (detail.code ?? body.code ?? 'http_error');
    const message: string =
      typeof detail === 'string'
        ? detail
        : (detail.message ?? detail.error ?? body.message ?? `HTTP ${r.status}`);
    throw new ApiError(r.status, code, message);
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}
