import { useEffect, useState } from 'react';

export interface ReportHeaderProps {
  left: string;
  right: string;
  printHref?: string;
}

function readScrollProgress(): number {
  if (typeof document === 'undefined') return 0;
  const el = document.scrollingElement ?? document.documentElement;
  const scrollable = el.scrollHeight - el.clientHeight;
  if (scrollable <= 0) return 0;
  const ratio = el.scrollTop / scrollable;
  if (Number.isNaN(ratio)) return 0;
  return Math.max(0, Math.min(1, ratio));
}

function useScrollProgress(): number {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let frame = 0;
    const tick = () => {
      frame = 0;
      setProgress(readScrollProgress());
    };
    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(tick);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);
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
  const progress = useScrollProgress();
  return (
    <div className="report-furniture__header">
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
