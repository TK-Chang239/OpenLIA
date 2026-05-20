import { useEffect, useState } from "react";
import type { JSX } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  GREETING_BANK,
  GREETING_BANK_ZH_TW,
  pickGreeting,
  pickGreetingBank,
  localDaySeed,
  timeOfDayGreeting,
} from "./home/greetings";
import { formatDateStamp } from "./home/dateStamp";
import { MorningBriefingSnapshotCard } from "./home/MorningBriefingSnapshotCard";
import { TickerStrip } from "./home/TickerStrip";
import { PortfolioGlanceCard } from "./home/PortfolioGlanceCard";
import { SuggestedGrid } from "./home/SuggestedGrid";
import { RecentStrip } from "./home/RecentStrip";
import { useAuth } from "../auth/AuthContext";

const STAGGER = 0.06;

function firstName(displayName: string | null | undefined, fallback: string): string {
  if (!displayName) return fallback;
  const trimmed = displayName.trim();
  if (!trimmed) return fallback;
  return trimmed.split(/\s+/)[0];
}

export default function Home(): JSX.Element {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [now, setNow] = useState<Date>(() => new Date());

  // Refresh the date stamp once per minute so a long-open tab doesn't show
  // a stale day after midnight crosses.
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const bank = pickGreetingBank(GREETING_BANK, GREETING_BANK_ZH_TW);
  const phrase = pickGreeting(bank, localDaySeed(now));
  const [pre, post] = phrase.template.split("{accent}");
  const tod = timeOfDayGreeting(now);
  const name = firstName(user?.display_name, t("welcome.greeting_hello"));

  return (
    <div className="mx-auto w-full max-w-[760px] px-8 pt-10 pb-16 flex flex-col gap-7">
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, ease: "easeOut" }}
        className="flex flex-col gap-[14px]"
      >
        <span className="inline-flex items-center gap-[10px] font-mono text-[10px] tracking-[0.14em] uppercase text-text-tertiary before:content-[''] before:w-[22px] before:h-px before:bg-border-strong">
          {formatDateStamp(now)}
        </span>
        <h1 className="m-0 font-display text-[52px] leading-[1.05] tracking-[-0.025em] font-medium text-text-primary">
          {tod}, {name}.<br />
          {pre}
          <em className="font-serif font-normal italic text-feedback-success">
            {phrase.accent}
          </em>
          {post}
        </h1>
      </motion.div>

      <Block delay={1}>
        <MorningBriefingSnapshotCard />
      </Block>
      <Block delay={2}>
        <TickerStrip />
      </Block>
      <Block delay={3}>
        <PortfolioGlanceCard />
      </Block>
      <Block delay={4}>
        <SuggestedGrid />
      </Block>
      <Block delay={5}>
        <RecentStrip />
      </Block>
    </div>
  );
}

function Block({
  delay,
  children,
}: {
  delay: number;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: "easeOut", delay: delay * STAGGER }}
    >
      {children}
    </motion.div>
  );
}
