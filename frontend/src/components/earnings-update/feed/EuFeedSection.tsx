import type { ReactNode } from "react";

interface Props {
  label: string;
  count?: number | null;
  children: ReactNode;
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

export function EuFeedSection({ label, count, children }: Props) {
  return (
    <section>
      <div className="font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-text-tertiary] mt-6 mb-2.5 flex items-center gap-2.5">
        <span>{label}</span>
        <span className="flex-1 h-px bg-[--color-border-subtle]" />
        {count !== null && count !== undefined ? (
          <span className="text-[--color-text-tertiary]" data-testid="eu-section-count">
            {pad2(count)}
          </span>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export function EuSectionEmpty({ message }: { message: string }) {
  return (
    <div className="py-8 px-4 text-center font-mono text-[11px] tracking-[0.12em] uppercase text-[--color-text-tertiary] border border-dashed border-[--color-border-subtle] rounded-[10px] my-2">
      {message}
    </div>
  );
}
