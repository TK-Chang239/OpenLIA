import type { VerdictCopy } from "./types";

export const verdictCopy: VerdictCopy = {
  metaParts: [
    "Panic Thermometer",
    "Severe · 3 of 5 red",
    "Composite 3.2 / 5.0",
    "Δ 7-day · +1 panel",
  ],
  headline:
    "The wage-Fed loop is the actionable signal. Oil duration is the slow burner. Diplomacy is the optionality.",
  paragraphs: [
    {
      parts: [
        { kind: "text", value: "Two of three reds are tightly correlated: " },
        { kind: "strong", value: "D3 (hawkish pivot)" },
        { kind: "text", value: " is a direct response to " },
        { kind: "strong", value: "D4 (second 0.6% AHE print)" },
        {
          kind: "text",
          value: '. If May AHE drops back below 0.5%, expect Powell to walk back "persistent" within two weeks and both panels to amber together. ',
        },
        { kind: "strong", value: "D1 (oil)" },
        {
          kind: "text",
          value:
            " is the slow burner — 47 days into a streak that doesn't trigger 2022-playbook for another 43 days; the threshold is the lever, not the price. ",
        },
        { kind: "strong", value: "D5 (diplomacy)" },
        {
          kind: "text",
          value:
            " still has 8 days of runway and zero escalation matches; this is where you have optionality. Composite drops to ",
        },
        { kind: "strong", value: "High (2 red)", tone: "warn" },
        {
          kind: "text",
          value:
            " on either a sub-0.5% AHE print or a Hormuz framework signing. The reverse path — ",
        },
        { kind: "strong", value: "Crisis (4 red)", tone: "bad" },
        { kind: "text", value: " — only requires Michigan 5Y to clear " },
        { kind: "strong", value: "3.0%" },
        { kind: "text", value: ", which the Apr 25 print missed by 0.1pp." },
      ],
    },
  ],
  tags: [
    { label: "→ Cross-check Macro Research summary", href: "/macro-research" },
    { label: "→ D4 Wage panel", href: "#wage" },
    { label: "→ D3 Fed panel", href: "#fed" },
    { label: "→ D1 Oil panel", href: "#oil" },
  ],
  generatedAt: "06:42",
  confidence: 78,
};
