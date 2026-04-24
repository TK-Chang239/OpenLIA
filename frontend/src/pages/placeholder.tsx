import type { JSX } from "react";

interface PagePlaceholderProps {
  title: string;
}

export function PagePlaceholder({ title }: PagePlaceholderProps): JSX.Element {
  return (
    <section className="min-h-full grid place-items-center p-8">
      <div className="rounded-lg border border-border-subtle bg-bg-elevated px-8 py-10 text-center">
        <span className="ol-label-sm">PAGE_NOT_READY</span>
        <h1 className="mt-2 font-display text-[24px] font-medium text-text-primary">
          {title}
        </h1>
      </div>
    </section>
  );
}
