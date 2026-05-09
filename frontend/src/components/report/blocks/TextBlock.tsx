import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ComponentPropsWithoutRef } from 'react';

export interface TextBlockProps {
  content: string;
}

// Combined matcher: signed-percent (e.g., +12.4%) OR citation [n] OR [n,m].
const TOKEN = /([+-]\d+(?:\.\d+)?%)|\[(\d+(?:\s*,\s*\d+)*)\]/g;

function decorate(text: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  TOKEN.lastIndex = 0;
  while ((match = TOKEN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const [whole, signedPct, citeIds] = match;
    if (signedPct) {
      const cls = signedPct.startsWith('+')
        ? 'report-number--positive'
        : 'report-number--negative';
      parts.push(
        <span key={`${match.index}-${signedPct}`} className={cls}>
          {signedPct}
        </span>,
      );
    } else if (citeIds) {
      const ids = citeIds.split(/\s*,\s*/);
      parts.push(
        <sup key={`${match.index}-cite`} className="report-cite">
          [
          {ids.map((id, i) => (
            <span key={id}>
              {i > 0 ? ',' : null}
              <a href={`#cite-${id}`} className="report-cite__link">
                {id}
              </a>
            </span>
          ))}
          ]
        </sup>,
      );
    }
    lastIndex = match.index + whole.length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function renderChildren(children: React.ReactNode): React.ReactNode {
  if (typeof children === 'string') return decorate(children);
  if (Array.isArray(children)) return children.map(renderChildren);
  return children;
}

export function TextBlock({ content }: TextBlockProps) {
  return (
    <div className="report-text">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children, ...rest }: ComponentPropsWithoutRef<'p'>) => (
            <p {...rest}>{renderChildren(children)}</p>
          ),
          li: ({ children, ...rest }: ComponentPropsWithoutRef<'li'>) => (
            <li {...rest}>{renderChildren(children)}</li>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
