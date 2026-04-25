import { motion } from "framer-motion";
import { useReducedMotion } from "../../hooks/useReducedMotion";

interface Chip {
  label: string;
  value: string;
}

interface Props {
  greeting: string;
  subtext: string;
  chips: Chip[];
  onChipClick: (value: string) => void;
}

export function WelcomeOverlay({ greeting, subtext, chips, onChipClick }: Props): JSX.Element {
  const reduce = useReducedMotion();
  const overlayDuration = reduce ? 0 : 0.2;
  const chipDuration = reduce ? 0 : 0.22;

  return (
    <motion.div
      data-testid="welcome-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, y: reduce ? 0 : -12 }}
      transition={{ duration: overlayDuration, ease: "easeOut" }}
      className="relative flex h-full w-full flex-col items-center justify-center px-6"
      style={{
        backgroundImage:
          "radial-gradient(circle, var(--color-border-subtle) 1px, transparent 1px)",
        backgroundSize: "28px 28px",
      }}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 65% 45% at 50% 65%, var(--color-accent-subtle) 0%, transparent 70%)",
          opacity: 0.6,
        }}
      />
      <h1
        className="relative text-center text-[30px] text-[--color-text-primary]"
        style={{ fontFamily: "DM Serif Display, serif" }}
      >
        {greeting}
      </h1>
      {subtext ? (
        <p className="relative mt-2 text-center text-md text-[--color-text-secondary]">{subtext}</p>
      ) : null}
      {chips.length > 0 ? (
        <div className="relative mt-8 flex max-w-[540px] flex-wrap justify-center gap-2">
          {chips.map((c, idx) => (
            <motion.button
              key={c.label}
              type="button"
              onClick={() => onChipClick(c.value)}
              initial={{ opacity: 0, y: reduce ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: chipDuration,
                ease: "easeOut",
                delay: reduce ? 0 : 0.2 + idx * 0.05,
              }}
              whileHover={
                reduce
                  ? undefined
                  : { scale: 1.02, transition: { type: "spring", stiffness: 400, damping: 20 } }
              }
              className="rounded-full border border-[--color-border-secondary]/60 bg-[--color-bg-elevated]/80 px-3.5 py-2 text-sm text-[--color-text-secondary] backdrop-blur-sm hover:border-[--color-accent-primary]/40 hover:bg-[--color-accent-subtle]/50 hover:text-[--color-accent-primary]"
            >
              {c.label}
            </motion.button>
          ))}
        </div>
      ) : null}
    </motion.div>
  );
}
