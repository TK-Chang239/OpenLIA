import { useEffect, useState } from "react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

export function CodeRenderer({ source }: { source: FileSource }): JSX.Element {
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    fetch(sourceUrl(source), { credentials: "same-origin" })
      .then((r) => r.text())
      .then(setText);
  }, [source]);

  if (text === null) return <div className="animate-pulse p-6">Loading…</div>;
  const lines = text.split("\n");
  return (
    <div className="flex text-sm">
      <div className="flex-shrink-0 select-none border-r border-[--color-border-subtle] bg-[--color-bg-base] px-4 py-4 text-right font-mono text-[--color-text-tertiary]">
        {lines.map((_, i) => (
          <div key={i}>{i + 1}</div>
        ))}
      </div>
      <pre className="flex-1 overflow-x-auto whitespace-pre bg-[--color-bg-code] px-4 py-4 font-mono text-[--color-text-code]">
        {text}
      </pre>
    </div>
  );
}
