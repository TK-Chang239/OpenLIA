import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbStreamState } from "../../../hooks/useMbRunStream";

import { deriveMbPhase, PHASE_ORDER } from "./mbPhase";

interface Props {
  stream: MbStreamState;
}

function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  const startRef = useRef<number | null>(null);
  useEffect(() => {
    if (!active) return;
    startRef.current = Date.now();
    setSeconds(0);
    const id = setInterval(() => {
      if (startRef.current != null) {
        setSeconds(Math.floor((Date.now() - startRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(id);
  }, [active]);
  return seconds;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function subjectFromEvents(stream: MbStreamState): string | null {
  for (const event of stream.events) {
    if (event.type === "run.started") {
      const subject = event.payload.subject;
      if (typeof subject === "string" && subject.trim()) return subject;
    }
  }
  return null;
}

const PIP_CLASS: Record<string, string> = {
  done: "bg-[--color-accent-primary]",
  active: "bg-[rgba(var(--color-accent-primary-rgb),0.4)]",
  pending: "bg-[--color-surface-active]",
};

export function MbGeneratingCard({ stream }: Props) {
  const { t } = useTranslation();
  const phase = deriveMbPhase(stream.events);
  const elapsed = useElapsedSeconds(stream.status === "streaming");
  const title =
    subjectFromEvents(stream) ?? t("morning_briefing.feed.gen.title_fallback");
  const terminal = stream.status !== "streaming";

  return (
    <article
      data-testid="mb-generating-card"
      className="relative overflow-hidden rounded-[12px] bg-[--color-bg-elevated] border border-[rgba(var(--color-accent-primary-rgb),0.55)] px-[26px] py-5 flex flex-col gap-3.5"
    >
      <span
        aria-hidden
        className="absolute top-0 left-0 right-0 h-px animate-lcg-scan"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(var(--color-accent-primary-rgb),0.85), transparent)",
        }}
      />

      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success] font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
          {t("morning_briefing.feed.gen.badge")}
        </span>
        <span
          aria-label={t("morning_briefing.feed.gen.elapsed_aria")}
          className="ml-auto font-mono text-[11px] text-[--color-text-tertiary] tabular-nums tracking-[0.04em]"
        >
          {formatElapsed(elapsed)}
        </span>
      </div>

      <h2 className="text-[24px] font-semibold tracking-[-0.01em] m-0 text-[--color-text-primary] leading-[1.2]">
        {title}
      </h2>

      <div className="flex items-center gap-3 min-h-[22px]">
        <span className="w-[15px] h-[15px] rounded-full border-[1.6px] border-[--color-border-strong] border-t-[--color-accent-primary] animate-spin flex-shrink-0" />
        <span className="text-[15px] font-medium text-[--color-text-primary]">
          {t(phase.labelKey)}
        </span>
        <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success] pl-3 border-l border-[--color-border-subtle] truncate max-w-[280px]">
          {phase.monoCode}
        </span>
      </div>

      <div
        aria-hidden
        className="relative h-[3px] bg-[--color-surface-active] rounded-full overflow-hidden"
      >
        <span
          className="absolute top-0 bottom-0 w-[32%] animate-lcg-sweep"
          style={{
            background:
              "linear-gradient(90deg, rgba(var(--color-accent-primary-rgb),0), rgba(var(--color-accent-primary-rgb),0.9), rgba(var(--color-accent-primary-rgb),0))",
          }}
        />
      </div>

      <div className="flex items-center gap-1.5" data-testid="mb-gen-pips">
        {PHASE_ORDER.map((key) => (
          <span
            key={key}
            data-pip={key}
            data-state={phase.pips[key]}
            className={`flex-1 h-[3px] rounded-full ${PIP_CLASS[phase.pips[key]]}`}
          />
        ))}
      </div>

      <div className="flex mt-0.5">
        <button
          type="button"
          onClick={() => void stream.cancel()}
          disabled={terminal}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] text-[13px] hover:text-[--color-text-primary] hover:border-[--color-border-strong] disabled:opacity-50 transition-colors duration-[--duration-normal]"
        >
          <X size={13} /> {t("morning_briefing.feed.gen.cancel")}
        </button>
      </div>
    </article>
  );
}
