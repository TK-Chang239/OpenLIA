import { useEffect, useState } from "react";
import type { JSX } from "react";
import { AnimatePresence, motion } from "framer-motion";

// Demo-only entry modal. Mounted from AppLayout under VITE_DEMO_MODE and shown
// once when the demo app loads, so a first-time visitor immediately understands
// the whole site is illustrative and nothing here is real. Dismiss with the
// button, the backdrop, or Escape; it does not reappear on client-side nav
// (AppLayout stays mounted), only on a full reload.
export default function DemoIntroModal(): JSX.Element {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          onClick={() => setOpen(false)}
          role="presentation"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="demo-intro-title"
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            className="w-full max-w-[440px] rounded-[14px] border border-border-strong bg-bg-elevated p-7 shadow-2xl"
          >
            <span className="inline-flex items-center gap-[8px] font-mono text-[10px] tracking-[0.14em] uppercase text-text-tertiary">
              <span
                aria-hidden="true"
                className="w-[6px] h-[6px] rounded-full bg-accent-primary"
              />
              Demo
            </span>
            <h2
              id="demo-intro-title"
              className="mt-3 mb-2 font-display text-[26px] leading-[1.15] tracking-[-0.02em] font-medium text-text-primary"
            >
              You&apos;re exploring a demo.
            </h2>
            <p className="m-0 text-[14px] leading-[1.55] text-text-secondary">
              This is a self-contained preview of OpenLIA. Every report, number, and
              data point is{" "}
              <strong className="font-medium text-text-primary">
                illustrative sample data
              </strong>{" "}
              — not real market data and not investment advice. Nothing you do here is
              saved.
            </p>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                autoFocus
                onClick={() => setOpen(false)}
                className="rounded-md bg-accent-primary px-4 py-2 text-[13px] font-medium text-text-on-accent transition-colors duration-normal ease-out hover:bg-accent-hover"
              >
                Explore the demo
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
