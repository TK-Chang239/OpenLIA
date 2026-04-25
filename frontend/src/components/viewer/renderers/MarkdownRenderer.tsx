import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { type FileSource } from "../FileViewerContext";
import { useFileFetch } from "./useFileFetch";
import { RendererEmpty, RendererError, RendererLoading } from "./RendererStates";
import { CodeBlock } from "../../chat/CodeBlock";

export function MarkdownRenderer({ source }: { source: FileSource }): JSX.Element {
  const { status, data, error, retry } = useFileFetch<string>(source, {
    parse: (raw) => raw,
  });

  if (status === "loading") return <RendererLoading />;
  if (status === "error")
    return <RendererError message={error?.message} onRetry={retry} />;
  if (status === "empty") return <RendererEmpty />;
  return (
    <article className="mx-auto max-w-[680px] px-6 py-5 text-md leading-relaxed text-[--color-text-primary] prose prose-sm dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ code: CodeBlock as never }}
      >
        {data ?? ""}
      </ReactMarkdown>
    </article>
  );
}
