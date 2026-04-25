import { type FileSource } from "../FileViewerContext";
import { useFileFetch } from "./useFileFetch";
import { RendererEmpty, RendererError, RendererLoading } from "./RendererStates";

export function CodeRenderer({ source }: { source: FileSource }): JSX.Element {
  const { status, data, error, retry } = useFileFetch<string>(source, {
    parse: (raw) => raw,
  });

  if (status === "loading") return <RendererLoading />;
  if (status === "error")
    return <RendererError message={error?.message} onRetry={retry} />;
  if (status === "empty" || !data) return <RendererEmpty />;
  const lines = data.split("\n");
  return (
    <div className="flex text-sm">
      <div
        aria-hidden="true"
        className="flex-shrink-0 select-none border-r border-[--color-border-subtle] bg-[--color-bg-base] px-4 py-4 text-right font-mono text-[--color-text-tertiary]"
      >
        {lines.map((_, i) => (
          <div key={i}>{i + 1}</div>
        ))}
      </div>
      <pre
        data-language="text"
        className="flex-1 overflow-x-auto whitespace-pre bg-[--color-bg-code] px-4 py-4 font-mono text-[--color-text-code]"
      >
        <code className="language-text">{data}</code>
      </pre>
    </div>
  );
}
