import { motion, useReducedMotion } from "framer-motion";
import type { JSX } from "react";
import { TrendingUp } from "lucide-react";

import {
  ER_GREETING_BANK,
  pickGreeting,
  localDaySeed,
  timeOfDayGreeting,
} from "../../pages/departments/equity-research/greetings";
import type { ReportLength, ReportMode } from "../../api/equity-research";

const MODE_PILL_LABEL: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation",
  stock_update: "Stock Update",
  sector_research: "Sector Research",
};
const LENGTH_PILL_LABEL: Record<ReportLength, string> = {
  concise: "Concise",
  normal: "Normal",
  elaborative: "Elaborative",
};

interface Props {
  firstName: string;
  mode: ReportMode;
  length: ReportLength;
  onModeRowClick: () => void;
  now?: Date;
}

export function WelcomeStage({
  firstName,
  mode,
  length,
  onModeRowClick,
  now = new Date(),
}: Props): JSX.Element {
  const reduce = useReducedMotion();
  const phrase = pickGreeting(ER_GREETING_BANK, localDaySeed(now));
  const [pre, post] = phrase.template.split("{accent}");
  const tod = timeOfDayGreeting(now);

  const stagger = (delay: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.4, ease: "easeOut" as const, delay },
  });

  return (
    <div
      className="flex flex-1 flex-col items-center justify-center gap-[22px] px-8 min-h-[420px]"
      data-testid="er-welcome-stage"
    >
      <motion.div
        {...stagger(0)}
        className="flex h-14 w-14 items-center justify-center rounded-[14px] bg-[--color-accent-primary] text-[--color-accent-on] shadow-[0_0_24px_rgba(212,255,0,0.35)]"
        aria-hidden="true"
      >
        <TrendingUp size={28} strokeWidth={1.6} />
      </motion.div>

      <motion.div
        {...stagger(0.06)}
        className="flex flex-col items-center gap-2"
      >
        <span className="font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-text-tertiary]">
          {tod}, {firstName}
        </span>
        <h1 className="m-0 max-w-[640px] text-center font-display text-[32px] font-medium leading-[1.15] tracking-[-0.02em] text-[--color-text-primary]">
          {pre}
          <em className="font-serif font-normal italic text-[--color-feedback-success]">
            {phrase.accent}
          </em>
          {post}
        </h1>
      </motion.div>

      <motion.p
        {...stagger(0.12)}
        className="m-0 max-w-[520px] text-center text-[15px] leading-[1.55] text-[--color-text-secondary]"
      >
        Initiate coverage on a name, refresh a thesis after an event, or take a
        sector apart from the top down.
      </motion.p>

      <motion.button
        {...stagger(0.18)}
        type="button"
        onClick={onModeRowClick}
        aria-label="Change report mode and length"
        className="inline-flex items-center gap-2 rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1.5 pl-2 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-secondary] hover:border-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
      >
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_6px_rgba(212,255,0,0.6)]"
        />
        <span>Mode</span>
        <span aria-hidden="true">·</span>
        <strong className="font-medium text-[--color-text-primary]">
          {MODE_PILL_LABEL[mode]}
        </strong>
        <span aria-hidden="true">·</span>
        <span>{LENGTH_PILL_LABEL[length]}</span>
      </motion.button>
    </div>
  );
}
