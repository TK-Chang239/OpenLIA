import { useState } from "react";
import type { PanelResult } from "../../api/panic-thermometer";

interface Props {
  result: PanelResult | undefined;
  onParamsChange?: (params: Record<string, string[]>) => void;
}

const KEYWORD_GROUPS: Array<{
  key: "dovish_keywords" | "neutral_keywords" | "hawkish_keywords" | "crisis_keywords";
  label: string;
}> = [
  { key: "dovish_keywords", label: "Dovish keywords" },
  { key: "neutral_keywords", label: "Neutral keywords" },
  { key: "hawkish_keywords", label: "Hawkish keywords" },
  { key: "crisis_keywords", label: "Crisis keywords" },
];

export function FedLanguageDashboard({ result, onParamsChange }: Props): JSX.Element {
  const matchedHeadline = String(result?.extras?.matched_headline ?? "");
  const matchedDate = String(result?.extras?.matched_date ?? "");
  const matchedPhrase = String(result?.extras?.matched_phrase ?? "");
  const daysSinceFomc = result?.extras?.days_since_fomc;

  const [groups, setGroups] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const g of KEYWORD_GROUPS) {
      const list = (result?.resolved_values?.[g.key] as string[] | undefined) ?? [];
      init[g.key] = Array.isArray(list) ? list.join("\n") : "";
    }
    return init;
  });

  const updateGroup = (k: string, text: string) => {
    setGroups((prev) => ({ ...prev, [k]: text }));
    if (onParamsChange) {
      const arr: Record<string, string[]> = {};
      for (const g of KEYWORD_GROUPS) {
        const src = k === g.key ? text : groups[g.key] ?? "";
        arr[g.key] = src
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean);
      }
      onParamsChange(arr);
    }
  };

  return (
    <div data-testid="fed-language-dashboard">
      <h4>Fed Language Tracker</h4>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <section>
          <strong>FOMC timeline:</strong>{" "}
          {daysSinceFomc == null ? "no event" : `${daysSinceFomc} days since FOMC`}
        </section>
        <section>
          <strong>Headline scanner:</strong>
          <div>{matchedHeadline || "(no match)"}</div>
          {matchedPhrase ? (
            <small>
              matched "{matchedPhrase}" {matchedDate ? `on ${matchedDate}` : ""}
            </small>
          ) : null}
        </section>
        <section
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}
        >
          {KEYWORD_GROUPS.map((g) => (
            <label key={g.key} style={{ display: "flex", flexDirection: "column" }}>
              <span>{g.label}</span>
              <textarea
                data-testid={`fed-kw-${g.key}`}
                value={groups[g.key] ?? ""}
                onChange={(e) => updateGroup(g.key, e.target.value)}
                rows={4}
              />
            </label>
          ))}
        </section>
      </div>
    </div>
  );
}
