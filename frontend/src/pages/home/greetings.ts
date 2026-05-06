/** Curated greeting phrase bank — each entry is a sentence with one word
 *  rendered in italic accent color. The picker is deterministic per local
 *  day, so the user sees a stable phrase that rotates at midnight. */

export interface GreetingPhrase {
  /** Full sentence with `{accent}` placeholder for the italic word. */
  template: string;
  /** Word that fills the placeholder, rendered in accent color + italic. */
  accent: string;
}

export const GREETING_BANK: readonly GreetingPhrase[] = [
  { template: "What's on the {accent} today?", accent: "tape" },
  { template: "What's printing across the {accent}?", accent: "wire" },
  { template: "What's setting the {accent} this morning?", accent: "tone" },
  { template: "What's getting {accent} at the open?", accent: "bid" },
  { template: "What's twitching on the {accent}?", accent: "screen" },
  { template: "What's quietly {accent} today?", accent: "compounding" },
  { template: "What moved the {accent} overnight?", accent: "ribbon" },
  { template: "What's the {accent} this morning?", accent: "print" },
  { template: "What's everyone {accent} this week?", accent: "watching" },
];

/** Pure picker — pulled out for unit tests. */
export function pickGreeting(
  bank: readonly GreetingPhrase[],
  daySeed: string,
): GreetingPhrase {
  if (bank.length === 0) {
    throw new Error("greeting bank cannot be empty");
  }
  let h = 0;
  for (let i = 0; i < daySeed.length; i++) {
    h = (h * 31 + daySeed.charCodeAt(i)) | 0;
  }
  const idx = ((h % bank.length) + bank.length) % bank.length;
  return bank[idx];
}

/** Local-day seed — `YYYY-MM-DD` in user's TZ. */
export function localDaySeed(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Time-of-day → "Good morning" / "Good afternoon" / "Good evening". */
export function timeOfDayGreeting(d: Date = new Date()): string {
  const h = d.getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
