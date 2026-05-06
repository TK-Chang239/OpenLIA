import type { JSX } from "react";
import { motion } from "framer-motion";
import { useReducedMotion } from "../../hooks/useReducedMotion";

export interface PullQuoteProps {
  text: string;
  attribution?: string | null;
  source?: string | null;
  timestamp?: string | null;
}

/** Parse the body of a `pullquote` fenced markdown block.
 *
 * Accepted shape:
 *
 *   <quote text — possibly multi-line>
 *   — ATTRIBUTION · SOURCE · TIMESTAMP
 *
 * The citation line begins with an em-dash (—) or two hyphens (--). Cells
 * after the dash are split by the middle-dot bullet (·) or | character.
 * Missing cells are returned as null; missing citation line means the body
 * is purely the quote text.
 */
export function parsePullQuote(source: string): PullQuoteProps {
  const lines = source.split(/\r?\n/);
  const citationIdx = lines.findIndex((line) => /^\s*(—|--)\s+/.test(line));
  if (citationIdx === -1) {
    return { text: source.trim(), attribution: null, source: null, timestamp: null };
  }
  const text = lines.slice(0, citationIdx).join("\n").trim();
  const citation = lines[citationIdx]
    .replace(/^\s*(—|--)\s+/, "")
    .trim();
  const cells = citation.split(/\s*[·|]\s*/).map((c) => c.trim());
  return {
    text,
    attribution: cells[0] || null,
    source: cells[1] || null,
    timestamp: cells[2] || null,
  };
}

export function PullQuote({ text, attribution, source, timestamp }: PullQuoteProps): JSX.Element {
  const citationParts = [attribution, source, timestamp].filter(Boolean);
  const reduce = useReducedMotion();
  return (
    <motion.figure
      initial={{ opacity: 0, y: reduce ? 0 : 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.2, ease: "easeOut" }}
      className="my-3 rounded-r-md py-[14px] pr-4 pl-4 text-[13px] leading-[1.6]"
      style={{
        borderLeft: "2px solid var(--color-accent-primary)",
        background: "rgba(var(--color-accent-primary-rgb), 0.07)",
        color: "var(--color-text-primary)",
      }}
    >
      <blockquote className="m-0">{text}</blockquote>
      {citationParts.length > 0 ? (
        <figcaption
          className="mt-[6px] font-mono text-[10px] uppercase"
          style={{
            letterSpacing: "var(--tracking-label)",
            color: "var(--color-text-tertiary)",
          }}
        >
          — {citationParts.join(" · ")}
        </figcaption>
      ) : null}
    </motion.figure>
  );
}
