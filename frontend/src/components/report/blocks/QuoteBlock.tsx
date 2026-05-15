import type { QuoteBlock as Block } from '../../../api/reports';
import { CitationRefs } from '../CitationRefs';

const HIGHLIGHT_RE = /==(.+?)==/g;

function renderHighlightedText(text: string): React.ReactNode {
  // Render `==marked==` segments as <mark>; everything else is plain text.
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = HIGHLIGHT_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<mark key={key++}>{match[1]}</mark>);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

export function QuoteBlock({ text, speaker, role, tag, timestamp, source_ids }: Omit<Block, 'type'>) {
  return (
    <figure className="report-quote">
      {speaker || role || tag || timestamp ? (
        <figcaption className="report-quote__meta">
          {speaker ? <span className="report-quote__speaker">{speaker}</span> : null}
          {role ? <span className="report-quote__role">{role}</span> : null}
          {tag ? (
            <span className="report-quote__tag" data-tone={tag.tone ?? 'neutral'}>
              {tag.label}
            </span>
          ) : null}
          {timestamp ? <span className="report-quote__timestamp">{timestamp}</span> : null}
        </figcaption>
      ) : null}
      <blockquote className="report-quote__body">
        {renderHighlightedText(text)}
        <CitationRefs ids={source_ids} />
      </blockquote>
    </figure>
  );
}
