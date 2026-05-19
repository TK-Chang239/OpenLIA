import type { JSX } from 'react';

export interface CitationRefsProps {
  ids: string[] | undefined;
}

/** Inline `[N]` markers that link to the citation list. Renders nothing when
 *  `ids` is empty or undefined. Each anchor points to `#cite-${id}` so the
 *  side-panel item with that anchor id can scroll into view.
 *
 *  The stored id format is `c14` (citation-prefixed), but the inline `[14]`
 *  markers in body text and the side-panel labels both display the bare
 *  numeric form — strip the leading `c` so all three surfaces agree. The
 *  anchor target keeps the full id since that's the DOM id the panel uses. */
function citationLabel(id: string): string {
  const stripped = id.startsWith('c') ? id.slice(1) : id;
  return `[${stripped}]`;
}

export function CitationRefs({ ids }: CitationRefsProps): JSX.Element | null {
  if (!ids || ids.length === 0) return null;
  return (
    <span className="citation-refs">
      {ids.map((id) => (
        <a
          key={id}
          className="citation-ref"
          href={`#cite-${id}`}
          aria-label={`Source ${id}`}
        >
          {citationLabel(id)}
        </a>
      ))}
    </span>
  );
}
