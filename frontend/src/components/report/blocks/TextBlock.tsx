import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ComponentPropsWithoutRef } from 'react';

export interface TextBlockProps {
  content: string;
}

const SIGNED_PCT = /([+-]\d+(?:\.\d+)?%)/g;

function colorSignedNumbers(text: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  SIGNED_PCT.lastIndex = 0;
  while ((match = SIGNED_PCT.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const value = match[1];
    const cls = value.startsWith('+')
      ? 'report-number--positive'
      : 'report-number--negative';
    parts.push(
      <span key={`${match.index}-${value}`} className={cls}>
        {value}
      </span>,
    );
    lastIndex = match.index + value.length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function renderChildren(children: React.ReactNode): React.ReactNode {
  if (typeof children === 'string') return colorSignedNumbers(children);
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
