import type { PanelId, PanelRule, PanelStatus } from "../../api/panic-thermometer";
import { FormulaInput } from "./FormulaInput";

interface Props {
  panel: PanelId;
  rules: PanelRule[];
  onChange: (next: PanelRule[]) => void;
}

const STATUSES: PanelStatus[] = ["green", "amber", "red", "dark_red"];

function move<T>(arr: T[], from: number, to: number): T[] {
  if (to < 0 || to >= arr.length) return arr;
  const next = [...arr];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function RuleEditor({ panel, rules, onChange }: Props): JSX.Element {
  const update = (idx: number, patch: Partial<PanelRule>) => {
    onChange(rules.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };
  const remove = (idx: number) => onChange(rules.filter((_, i) => i !== idx));
  const add = () =>
    onChange([
      ...rules,
      { status: "green", formula: "true", label: "" } satisfies PanelRule,
    ]);

  return (
    <div data-testid="rule-editor">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <strong>Rules</strong>
        <button type="button" onClick={add} data-testid="rule-add">
          Add rule
        </button>
      </div>
      <ol style={{ paddingLeft: "1.25rem" }}>
        {rules.map((rule, i) => (
          <li
            key={i}
            data-testid={`rule-${i}`}
            style={{ display: "flex", flexDirection: "column", gap: "0.25rem", padding: "0.25rem 0" }}
          >
            <div style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
              <button
                type="button"
                data-testid={`rule-up-${i}`}
                onClick={() => onChange(move(rules, i, i - 1))}
              >
                ↑
              </button>
              <button
                type="button"
                data-testid={`rule-down-${i}`}
                onClick={() => onChange(move(rules, i, i + 1))}
              >
                ↓
              </button>
              <select
                data-testid={`rule-status-${i}`}
                value={rule.status}
                onChange={(e) =>
                  update(i, { status: e.target.value as PanelStatus })
                }
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <input
                type="text"
                data-testid={`rule-label-${i}`}
                value={rule.label}
                placeholder="label"
                onChange={(e) => update(i, { label: e.target.value })}
                style={{ flex: 1 }}
              />
              <button
                type="button"
                data-testid={`rule-delete-${i}`}
                onClick={() => remove(i)}
              >
                Delete
              </button>
            </div>
            <FormulaInput
              panel={panel}
              value={rule.formula}
              onChange={(formula) => update(i, { formula })}
            />
          </li>
        ))}
      </ol>
    </div>
  );
}
