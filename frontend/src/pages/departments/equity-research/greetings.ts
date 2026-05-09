import {
  type GreetingPhrase,
  pickGreeting,
  localDaySeed,
  timeOfDayGreeting,
} from "../../home/greetings";

export const ER_GREETING_BANK: readonly GreetingPhrase[] = [
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

export { pickGreeting, localDaySeed, timeOfDayGreeting };
export type { GreetingPhrase };
