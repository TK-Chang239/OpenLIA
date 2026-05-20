import {
  type GreetingPhrase,
  pickGreeting,
  pickGreetingBank,
  localDaySeed,
  timeOfDayGreeting,
} from "../../home/greetings";

const ER_GREETING_BANK_EN: readonly GreetingPhrase[] = [
  { template: "What name are we {accent} today?", accent: "underwriting" },
  { template: "Which company deserves a fresh {accent}?", accent: "thesis" },
  { template: "Where is the market {accent}?", accent: "wrong" },
  { template: "What's worth a deeper {accent}?", accent: "look" },
  { template: "Which sector is {accent} today?", accent: "mispriced" },
  { template: "What's hiding in plain {accent}?", accent: "sight" },
  { template: "Whose story is the tape {accent}?", accent: "missing" },
  { template: "Which name is quietly {accent}?", accent: "compounding" },
  { template: "What deserves a second {accent}?", accent: "read" },
];

const ER_GREETING_BANK_ZH_TW: readonly GreetingPhrase[] = [
  { template: "今天要替哪一檔{accent}？", accent: "建立覆蓋" },
  { template: "哪一家公司值得重新檢視{accent}？", accent: "投資觀點" },
  { template: "市場現在在哪裡{accent}？", accent: "誤判" },
  { template: "什麼值得再深入{accent}？", accent: "研究" },
  { template: "今天哪個產業最被{accent}？", accent: "錯估" },
  { template: "什麼真相藏在{accent}之中？", accent: "明面" },
  { template: "哪一檔股票的故事{accent}了？", accent: "被忽略" },
  { template: "哪一檔正默默地在{accent}？", accent: "複利成長" },
  { template: "什麼值得我們再{accent}一次？", accent: "細讀" },
];

/** Language-aware getter — returns the English or Traditional Chinese
 *  bank to match the current UI language (read from
 *  document.documentElement.dataset.lang, kept in sync by i18n
 *  setUiLanguage). The picker is unchanged across languages so the
 *  same day-seed lands on the same phrase index regardless of locale. */
export function getErGreetingBank(): readonly GreetingPhrase[] {
  return pickGreetingBank(ER_GREETING_BANK_EN, ER_GREETING_BANK_ZH_TW);
}

/** Static English bank — exported for tests + back-compat. New callers
 *  should use getErGreetingBank() so picks switch with the UI language. */
export const ER_GREETING_BANK = ER_GREETING_BANK_EN;

export { pickGreeting, localDaySeed, timeOfDayGreeting };
export type { GreetingPhrase };
