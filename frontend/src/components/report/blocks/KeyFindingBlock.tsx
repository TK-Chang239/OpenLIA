import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { CitationRefs } from '../CitationRefs';

export interface KeyFindingBlockProps {
  type: 'key_finding';
  content: string;
  source_ids?: string[];
}

export function KeyFindingBlock({ content, source_ids }: KeyFindingBlockProps) {
  return (
    <aside className="key-finding" role="note">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      <CitationRefs ids={source_ids} />
    </aside>
  );
}
