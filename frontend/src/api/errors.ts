import { ApiError } from "./client";
import type { BannerVariant } from "../components/primitives/Banner";

export interface TransportErrorMapping {
  message: string;
  variant: BannerVariant;
}

const OFFLINE: TransportErrorMapping = {
  message: "Can't reach the server. Check your connection.",
  variant: "error",
};

const SERVER_ERROR: TransportErrorMapping = {
  message: "Something went wrong on our end. Please try again.",
  variant: "error",
};

const UNKNOWN: TransportErrorMapping = {
  message: "Unexpected error. Please try again.",
  variant: "error",
};

/**
 * Map a thrown error from `fetchJson` to a banner-ready message + variant.
 *
 * `fetchJson` wraps native `TypeError` (offline / DNS failure) as
 * `ApiError(0, …)` before re-throwing, so transport failures arrive as
 * status-zero ApiErrors. We still accept a raw `TypeError` to be safe.
 */
export function mapTransportError(err: unknown): TransportErrorMapping {
  if (err instanceof TypeError) return OFFLINE;
  if (err instanceof ApiError) {
    if (err.status === 0) return OFFLINE;
    if (err.status >= 500) return SERVER_ERROR;
  }
  return UNKNOWN;
}
