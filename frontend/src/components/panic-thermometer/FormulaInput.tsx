import { useEffect, useState } from "react";
import {
  parseFormula,
  type FormulaParseResponse,
  type PanelId,
} from "../../api/panic-thermometer";

interface Props {
  panel: PanelId;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function FormulaInput({ panel, value, onChange, placeholder }: Props): JSX.Element {
  const [parsed, setParsed] = useState<FormulaParseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!value.trim()) {
      setParsed(null);
      setError(null);
      return;
    }
    const handle = setTimeout(() => {
      parseFormula(value, panel)
        .then((res) => {
          setParsed(res);
          setError(res.ok ? null : (res.errors?.[0]?.message ?? "parse error"));
        })
        .catch((err) => setError(err instanceof Error ? err.message : String(err)));
    }, 300);
    return () => clearTimeout(handle);
  }, [value, panel]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      <input
        type="text"
        data-testid="formula-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "e.g. price > price_threshold"}
        style={{
          width: "100%",
          fontFamily: "var(--font-mono, monospace)",
          padding: "0.25rem",
        }}
      />
      {error ? (
        <div
          role="alert"
          data-testid="formula-error"
          style={{ color: "var(--color-feedback-error)", fontSize: "0.75rem" }}
        >
          {error}
        </div>
      ) : parsed?.ok && parsed.identifiers ? (
        <div data-testid="formula-identifiers" style={{ fontSize: "0.75rem" }}>
          {parsed.identifiers.map((id) => (
            <span
              key={id}
              style={{
                display: "inline-block",
                padding: "1px 6px",
                margin: "1px 2px",
                background: "var(--color-bg-elevated)",
                borderRadius: 4,
                border: "1px solid var(--color-border-subtle)",
              }}
            >
              {id}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
