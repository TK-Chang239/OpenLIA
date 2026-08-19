/**
 * Render engine narrative text whose `[^source_id]` ledger markers can be
 * resolved against a payload-supplied citation table. Markers with a match
 * become superscript links (numbered by the citation's position in the
 * table); markers without a match are stripped so raw tokens never reach
 * the reader. With no table at all this degrades to a plain strip.
 */
import { createContext, useContext } from "react";
import type { ReactNode } from "react";

export interface DashCitation {
  source_id: string;
  title?: string | null;
  url?: string | null;
}

/** Payload-level citation table, provided at a dashboard view's root so
 * deeply nested prose widgets can resolve markers without prop drilling. */
export const CitationTableContext = createContext<DashCitation[] | null>(null);

/** Hook returning a prose renderer: strings get their citation markers
 * linkified against the context table; non-string nodes pass through. */
export function useLinkedProse(): (value: ReactNode) => ReactNode {
  const citations = useContext(CitationTableContext);
  return (value: ReactNode) =>
    typeof value === "string" ? linkifyCitations(value, citations) : value;
}

const MARKER_RE = /\s*\[\^([a-z0-9_]+)\]/g;

export function linkifyCitations(
  text: string,
  citations?: DashCitation[] | null,
): ReactNode {
  const table = new Map<string, { index: number; citation: DashCitation }>();
  (citations ?? []).forEach((c, i) => {
    if (c?.source_id && !table.has(c.source_id)) {
      table.set(c.source_id, { index: i + 1, citation: c });
    }
  });

  const parts: ReactNode[] = [];
  let cursor = 0;
  MARKER_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = MARKER_RE.exec(text)) !== null) {
    if (match.index > cursor) parts.push(text.slice(cursor, match.index));
    cursor = match.index + match[0].length;
    const hit = table.get(match[1]);
    if (!hit) continue; // unknown id -> stripped
    const label = `[${hit.index}]`;
    const title = hit.citation.title ?? undefined;
    parts.push(
      hit.citation.url ? (
        <sup key={`${match.index}-${match[1]}`} className="cite-sup">
          <a href={hit.citation.url} target="_blank" rel="noopener noreferrer" title={title}>
            {label}
          </a>
        </sup>
      ) : (
        <sup key={`${match.index}-${match[1]}`} className="cite-sup" title={title}>
          {label}
        </sup>
      ),
    );
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  if (parts.length === 0) return "";
  return parts;
}
