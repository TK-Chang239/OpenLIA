import { useEffect, useRef, useState } from 'react';

export interface ReportHeaderProps {
  left: string;
  right: string;
  printHref?: string;
}

function findScrollAncestor(start: HTMLElement | null): HTMLElement | Window {
  if (typeof window === 'undefined') return globalThis as unknown as Window;
  let el: HTMLElement | null = start?.parentElement ?? null;
  while (el && el !== document.body && el !== document.documentElement) {
    const style = window.getComputedStyle(el);
    const oy = style.overflowY;
    if ((oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight) {
      return el;
    }
    el = el.parentElement;
  }
  return window;
}

function readProgress(source: HTMLElement | Window): number {
  if (source === window) {
    const el = document.scrollingElement ?? document.documentElement;
    const scrollable = el.scrollHeight - el.clientHeight;
    if (scrollable <= 0) return 0;
    return Math.max(0, Math.min(1, el.scrollTop / scrollable));
  }
  const el = source as HTMLElement;
  const scrollable = el.scrollHeight - el.clientHeight;
  if (scrollable <= 0) return 0;
  return Math.max(0, Math.min(1, el.scrollTop / scrollable));
}

function useScrollProgress(anchorRef: React.RefObject<HTMLElement>): number {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const source = findScrollAncestor(anchorRef.current);
    let frame = 0;
    const tick = () => {
      frame = 0;
      setProgress(readProgress(source));
    };
    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(tick);
    };
    onScroll();
    source.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      source.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [anchorRef]);
  return progress;
}

function PrinterIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 6 2 18 2 18 9" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" />
    </svg>
  );
}

export function ReportHeader({ left, right, printHref }: ReportHeaderProps) {
  const ref = useRef<HTMLDivElement>(null);
  const progress = useScrollProgress(ref);
  return (
    <div ref={ref} className="report-furniture__header">
      <span className="report-furniture__header-left">{left}</span>
      <span className="report-furniture__header-right">
        <span className="report-furniture__header-right-text">{right}</span>
        {printHref ? (
          <a
            href={printHref}
            target="_blank"
            rel="noopener noreferrer"
            className="report-furniture__print"
            title="Open print view"
            aria-label="Open print view"
          >
            <PrinterIcon />
          </a>
        ) : null}
      </span>
      <span
        className="report-furniture__progress"
        role="progressbar"
        aria-label="Report scroll progress"
        aria-valuenow={Math.round(progress * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span
          className="report-furniture__progress-fill"
          style={{ transform: `scaleX(${progress})` }}
        />
      </span>
    </div>
  );
}
