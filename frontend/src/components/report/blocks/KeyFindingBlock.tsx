import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface KeyFindingBlockProps {
  type: 'key_finding';
  content: string;
}

export function KeyFindingBlock({ content }: KeyFindingBlockProps) {
  return (
    <aside className="key-finding" role="note">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </aside>
  );
}
