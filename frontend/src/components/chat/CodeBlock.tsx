import type { ComponentPropsWithoutRef, JSX } from "react";

type CodeProps = ComponentPropsWithoutRef<"code"> & {
  inline?: boolean;
};

/**
 * Shared `code` renderer for ReactMarkdown. Handles inline backticks and
 * fenced code blocks; the language hint flows through as `language-{lang}`
 * so a future syntax-highlighter (highlight.js / shiki) can target it.
 */
export function CodeBlock({
  inline,
  className,
  children,
  ...rest
}: CodeProps): JSX.Element {
  const match = /language-(\w+)/.exec(className ?? "");
  const language = match?.[1];

  if (inline) {
    return (
      <code
        className={`rounded bg-[--color-bg-base] px-1 py-0.5 font-mono text-[12.5px] ${className ?? ""}`}
        {...rest}
      >
        {children}
      </code>
    );
  }

  return (
    <pre
      data-language={language}
      className="overflow-x-auto rounded-md bg-[--color-bg-base] px-3 py-3 font-mono text-[13px] leading-[1.55]"
    >
      <code className={`language-${language ?? "text"}`} {...rest}>
        {children}
      </code>
    </pre>
  );
}
