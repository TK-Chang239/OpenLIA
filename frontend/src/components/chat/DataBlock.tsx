import type { JSX } from "react";
import { motion } from "framer-motion";
import { useReducedMotion } from "../../hooks/useReducedMotion";

export interface DataRow {
  label: string;
  value: string;
  delta: string | null;
}

interface Props {
  rows: DataRow[];
}

/** Parse the pipe-delimited body of a `databloc` fenced markdown block.
 *
 * Accepted shapes per line (whitespace tolerated, blank lines skipped):
 *   LABEL | VALUE | DELTA
 *   LABEL | VALUE
 *
 * The DELTA cell may be empty, omitted, or prefixed with + / - / no sign;
 * the renderer infers polarity from the first non-whitespace char (+ → pos,
 * - → neg, anything else → neutral).
 */
export function parseDataBlock(source: string): DataRow[] {
  return source
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      const cells = line.split("|").map((c) => c.trim());
      const [label = "", value = "", delta = ""] = cells;
      return {
        label,
        value,
        delta: delta.length > 0 ? delta : null,
      };
    });
}

function deltaTone(delta: string): "pos" | "neg" | "neutral" {
  const head = delta.trim().charAt(0);
  if (head === "+") return "pos";
  if (head === "-" || head === "−") return "neg";
  return "neutral";
}

export function DataBlock({ rows }: Props): JSX.Element {
  const reduce = useReducedMotion();
  return (
    <motion.div
      role="table"
      aria-label="Data summary"
      initial={{ opacity: 0, y: reduce ? 0 : 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.2, ease: "easeOut" }}
      className="my-[10px] grid gap-y-[4px] gap-x-[18px] rounded-md border border-border-subtle px-3 py-[10px] font-mono text-[12px] tabular-nums"
      style={{
        gridTemplateColumns: "1fr auto auto",
        background: "var(--color-bg-input)",
        color: "var(--color-text-primary)",
      }}
    >
      {rows.map((row, i) => {
        const tone = row.delta ? deltaTone(row.delta) : "neutral";
        return (
          <div role="row" key={i} className="contents">
            <span
              role="cell"
              className="font-mono text-[10px] uppercase"
              style={{
                letterSpacing: "var(--tracking-label)",
                color: "var(--color-text-tertiary)",
              }}
            >
              {row.label}
            </span>
            <span role="cell" className="text-right font-medium">
              {row.value}
            </span>
            <span
              role="cell"
              className="text-right"
              style={{
                color:
                  tone === "pos"
                    ? "var(--color-feedback-success)"
                    : tone === "neg"
                      ? "var(--color-feedback-error)"
                      : "var(--color-text-secondary)",
              }}
            >
              {row.delta ?? ""}
            </span>
          </div>
        );
      })}
    </motion.div>
  );
}
