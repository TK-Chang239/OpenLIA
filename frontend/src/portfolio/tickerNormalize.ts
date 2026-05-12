import type { Market } from "./marketTypes";

export interface NormalizeResult {
  readonly ok: boolean;
  readonly ticker?: string;
  readonly error?: string;
}

const TWSE_NUMERIC = /^\d{3,6}$/;
const US_SUFFIX = /\.(US|NYSE|NASDAQ)$/i;
const TWSE_SUFFIX = /\.(TW|TWO)$/i;
const US_BARE = /^[A-Z][A-Z0-9.\-]*$/;

/** Normalize user input into the canonical EODHD symbol for the active market.
 *  Returns `{ok:false, error}` for inputs that don't belong to the market. */
export function normalizeTicker(raw: string, market: Market): NormalizeResult {
  const cleaned = raw.trim().toUpperCase();
  if (!cleaned) {
    return { ok: false, error: "Ticker is required" };
  }

  if (market === "tw") {
    if (TWSE_SUFFIX.test(cleaned)) {
      const base = cleaned.replace(TWSE_SUFFIX, "");
      return { ok: true, ticker: `${base}.TW` };
    }
    if (TWSE_NUMERIC.test(cleaned)) {
      return { ok: true, ticker: `${cleaned}.TW` };
    }
    return {
      ok: false,
      error: `${raw} is not a TWSE ticker — enter a 3-6 digit code or *.TW symbol.`,
    };
  }

  if (US_SUFFIX.test(cleaned)) {
    return { ok: true, ticker: cleaned.replace(US_SUFFIX, "") };
  }
  if (TWSE_SUFFIX.test(cleaned)) {
    return {
      ok: false,
      error: `${raw} looks like a TWSE ticker — switch to the TW portfolio to add it.`,
    };
  }
  if (US_BARE.test(cleaned)) {
    return { ok: true, ticker: cleaned };
  }
  return { ok: false, error: `${raw} is not a recognised US ticker.` };
}
