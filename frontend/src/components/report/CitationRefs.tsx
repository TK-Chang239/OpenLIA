import type { JSX } from 'react';

export interface CitationRefsProps {
  ids: string[] | undefined;
}

/** Inline `[N]` markers that link to the citation list. Renders nothing when
 *  `ids` is empty or undefined. Each anchor points to `#cite-${id}` so the
 *  side-panel item with that anchor id can scroll into view. */
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
          {`[${id}]`}
        </a>
      ))}
    </span>
  );
}
