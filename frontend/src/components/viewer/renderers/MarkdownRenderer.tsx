import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

export function MarkdownRenderer({ source }: { source: FileSource }): JSX.Element {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(sourceUrl(source), { credentials: "same-origin" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setText)
      .catch((e) => setError((e as Error).message));
  }, [source]);

  if (error) return <div className="p-6 text-sm text-[--color-feedback-error]">{error}</div>;
  if (text === null)
    return (
      <div className="animate-pulse space-y-2 p-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-4 rounded bg-[--color-surface-hover]" />
        ))}
      </div>
    );
  return (
    <article className="mx-auto max-w-[680px] px-6 py-5 text-md leading-relaxed text-[--color-text-primary] prose prose-sm dark:prose-invert">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </article>
  );
}
