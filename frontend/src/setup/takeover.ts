/**
 * On 409 wizard_session_active, prompt the user to take over the wizard
 * session and retry the original request once. The promptHandler is
 * supplied by the UI (modal); a no-op here would just rethrow.
 */
import { ApiError } from "../api/client";
import { takeover } from "../api/setup";

export type TakeoverPromptHandler = () => Promise<boolean>;

let _handler: TakeoverPromptHandler = async () => false;

export function setTakeoverPromptHandler(h: TakeoverPromptHandler): void {
  _handler = h;
}

export function getTakeoverPromptHandler(): TakeoverPromptHandler {
  return _handler;
}

export async function withTakeoverRetry<T>(call: () => Promise<T>): Promise<T> {
  try {
    return await call();
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      const body = err.body as { detail?: { code?: string } } | null;
      const code = body?.detail?.code;
      if (code === "wizard_session_active") {
        const ok = await _handler();
        if (ok) {
          await takeover();
          return await call();
        }
      }
    }
    throw err;
  }
}
