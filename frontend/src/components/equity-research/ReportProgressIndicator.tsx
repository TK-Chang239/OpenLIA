import { type JSX, useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface Props {
  /** Wall-clock ms timestamp when generation began. */
  startedAt: number | null;
  /** e.g. "stock_initiation". */
  mode: string;
  /** Ticker / company / sector typed by the user. */
  subject: string;
}

const STOCK_VERBS = [
  "Reconciling filings",
  "Crunching financials",
  "Cross-referencing peers",
  "Triangulating estimates",
  "Stress-testing assumptions",
  "Benchmarking comps",
  "Auditing the print",
  "Scrutinizing footnotes",
  "Modeling cash flows",
  "Parsing the 10-K",
  "Tabulating segments",
  "Profiling the operator",
  "Synthesizing the thesis",
  "Diligencing the print",
  "Underwriting the setup",
];

const SECTOR_VERBS = [
  "Mapping the cohort",
  "Sizing the TAM",
  "Stack-ranking peers",
  "Reading the tape",
  "Cross-referencing peers",
  "Triangulating estimates",
  "Benchmarking comps",
  "Synthesizing the thesis",
];

function reportTypeLabel(mode: string): string {
  if (mode === "stock_initiation") return "stock initiation report";
  if (mode === "stock_update") return "stock update";
  if (mode === "sector_research") return "sector research report";
  return "report";
}

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const VERB_INTERVAL_MS = 2200;

export function ReportProgressIndicator({
  startedAt,
  mode,
  subject,
}: Props): JSX.Element {
  const reduce = useReducedMotion();
  const [now, setNow] = useState<number>(() => Date.now());
  const [verbIdx, setVerbIdx] = useState(0);

  useEffect(() => {
    if (startedAt === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [startedAt]);

  const verbs = useMemo(
    () => (mode === "sector_research" ? SECTOR_VERBS : STOCK_VERBS),
    [mode],
  );

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(
      () => setVerbIdx((i) => (i + 1) % verbs.length),
      VERB_INTERVAL_MS,
    );
    return () => window.clearInterval(id);
  }, [reduce, verbs.length]);

  const trimmedSubject = subject.trim();
  const headline = trimmedSubject
    ? `Drafting the ${reportTypeLabel(mode)} on ${trimmedSubject}`
    : `Drafting your ${reportTypeLabel(mode)}`;

  const elapsedMs = startedAt === null ? 0 : now - startedAt;
  const verb = verbs[verbIdx % verbs.length];

  return (
    <motion.div
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className="flex flex-col gap-2"
      data-testid="er-report-progress"
      aria-live="polite"
    >
      <style>{`
        @keyframes er-shimmer {
          0%   { background-position: 200% 50%; }
          100% { background-position: -200% 50%; }
        }
        .er-shimmer-text {
          background: linear-gradient(
            90deg,
            var(--color-text-primary) 0%,
            var(--color-text-primary) 35%,
            var(--color-feedback-success) 50%,
            var(--color-text-primary) 65%,
            var(--color-text-primary) 100%
          );
          background-size: 200% 100%;
          background-clip: text;
          -webkit-background-clip: text;
          color: transparent;
          -webkit-text-fill-color: transparent;
          animation: er-shimmer 2.4s linear infinite;
        }
        .er-shimmer-sub {
          background: linear-gradient(
            90deg,
            var(--color-text-secondary) 0%,
            var(--color-text-secondary) 35%,
            var(--color-feedback-success) 50%,
            var(--color-text-secondary) 65%,
            var(--color-text-secondary) 100%
          );
          background-size: 200% 100%;
          background-clip: text;
          -webkit-background-clip: text;
          color: transparent;
          -webkit-text-fill-color: transparent;
          animation: er-shimmer 2.8s linear infinite;
        }
        @keyframes er-dot-pulse {
          0%, 100% { opacity: 0.3; transform: translateY(0); }
          50%      { opacity: 1;   transform: translateY(-2px); }
        }
        .er-typing-dots { display: inline-flex; align-items: center; gap: 4px; }
        .er-typing-dots span {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: var(--color-text-tertiary);
          animation: er-dot-pulse 1.2s ease-in-out infinite;
        }
        .er-typing-dots span:nth-child(2) { animation-delay: 200ms; }
        .er-typing-dots span:nth-child(3) { animation-delay: 400ms; }
        @media (prefers-reduced-motion: reduce) {
          .er-shimmer-text,
          .er-shimmer-sub {
            animation: none;
            color: var(--color-text-primary);
            -webkit-text-fill-color: var(--color-text-primary);
          }
          .er-shimmer-sub {
            color: var(--color-text-secondary);
            -webkit-text-fill-color: var(--color-text-secondary);
          }
          .er-typing-dots span { animation: none; opacity: 0.6; }
        }
      `}</style>

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p
          key={headline}
          className="er-shimmer-text m-0 font-display text-[14.5px] font-medium leading-[1.7]"
        >
          {headline}
        </p>
        <span className="font-mono text-[11px] tabular-nums tracking-[0.06em] text-[--color-text-tertiary]">
          {formatElapsed(elapsedMs)}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span
          key={verb}
          className="er-shimmer-sub font-mono text-[11px] tracking-[0.04em]"
        >
          {verb}
        </span>
        <span className="er-typing-dots" aria-hidden>
          <span />
          <span />
          <span />
        </span>
      </div>
    </motion.div>
  );
}
