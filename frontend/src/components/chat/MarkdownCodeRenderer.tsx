import type { ComponentPropsWithoutRef, JSX } from "react";
import { CodeBlock } from "./CodeBlock";
import { DataBlock, parseDataBlock } from "./DataBlock";
import { PullQuote, parsePullQuote } from "./PullQuote";

type CodeProps = ComponentPropsWithoutRef<"code"> & { inline?: boolean };

/** ReactMarkdown `code` renderer that intercepts our custom fenced
 *  languages (`databloc`, `pullquote`) before falling back to the standard
 *  `CodeBlock`. Inline backticks always go through `CodeBlock`. */
export function MarkdownCodeRenderer(props: CodeProps): JSX.Element {
  const { inline, className, children } = props;
  if (inline) {
    return <CodeBlock {...props} />;
  }

  const match = /language-(\w+)/.exec(className ?? "");
  const language = match?.[1];
  const text = String(children ?? "").replace(/\n$/, "");

  if (language === "databloc") {
    return <DataBlock rows={parseDataBlock(text)} />;
  }
  if (language === "pullquote") {
    const parsed = parsePullQuote(text);
    return <PullQuote {...parsed} />;
  }

  return <CodeBlock {...props} />;
}
