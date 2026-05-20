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

/** Traditional Chinese counterpart. Same shape, same accent slot. Tone
 *  matches the English bank's terse market-floor voice. CJK has no
 *  italic glyph so the green accent word is styled via the
 *  html[data-lang="zh-TW"] rule in global.css (bold + skew). */
export const GREETING_BANK_ZH_TW: readonly GreetingPhrase[] = [
  { template: "今天盤面上有什麼{accent}？", accent: "新題材" },
  { template: "今早盤前的{accent}是什麼？", accent: "風向" },
  { template: "今天哪一檔最受{accent}？", accent: "關注" },
  { template: "今天有什麼正在{accent}？", accent: "醞釀" },
  { template: "近期市場最在{accent}什麼？", accent: "看的" },
  { template: "今天螢幕上有什麼在{accent}？", accent: "跳動" },
  { template: "本週大家都在{accent}哪一檔？", accent: "盯著" },
  { template: "隔夜行情有什麼{accent}？", accent: "重點" },
  { template: "今天有什麼默默在{accent}？", accent: "累積" },
];

/** Resolve the appropriate greeting bank for the current UI language.
 *  Reads document.documentElement.dataset.lang (kept in sync by i18n
 *  setUiLanguage). Falls back to the English bank when unset. */
export function pickGreetingBank(
  enBank: readonly GreetingPhrase[],
  zhBank: readonly GreetingPhrase[],
): readonly GreetingPhrase[] {
  if (typeof document === "undefined") return enBank;
  return document.documentElement.dataset.lang === "zh-TW" ? zhBank : enBank;
}

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

/** Time-of-day → localized morning / afternoon / evening greeting.
 *  Honours the document-level language flag set by i18n setUiLanguage. */
export function timeOfDayGreeting(d: Date = new Date()): string {
  const h = d.getHours();
  const lang =
    typeof document !== "undefined" ? document.documentElement.dataset.lang : undefined;
  if (lang === "zh-TW") {
    if (h < 12) return "早安";
    if (h < 18) return "午安";
    return "晚安";
  }
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
