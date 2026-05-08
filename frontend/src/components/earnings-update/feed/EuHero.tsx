interface Props {
  reportsThisWeek: number | null;
  beats: number | null;
  misses: number | null;
  avgSurprise: string | null;
  avgLatency: string | null;
  watchlistEmpty: boolean;
}

const DASH = "—";

export function EuHero({
  reportsThisWeek,
  beats,
  misses,
  avgSurprise,
  avgLatency,
  watchlistEmpty,
}: Props) {
  const lede = watchlistEmpty
    ? "Add tickers to your watchlist and LIA will auto-generate reports as they release."
    : "Live coverage of every print across your watchlist. LIA reads the release, listens to the call, and revises the model.";

  return (
    <section className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-end pb-[22px] border-b border-[--color-border-subtle] mb-6">
      <div>
        <span
          className="inline-flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-feedback-success] mb-2.5"
          data-testid="eu-hero-eyebrow"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_0_4px_rgba(var(--color-accent-primary-rgb),0.18)]" />
          Earnings Update {String.fromCharCode(0xb7)} Department
        </span>
        <h1 className="text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] m-0 mb-2 text-[--color-text-primary]">
          This week in earnings
        </h1>
        <p className="text-base text-[--color-text-secondary] m-0 max-w-[620px] leading-[1.55]">
          {lede}
        </p>
      </div>
      <div className="flex gap-7">
        <Stat label="Reports this wk" value={reportsThisWeek ?? DASH} />
        <Stat
          label="Beats / Misses"
          value={
            beats === null || misses === null ? (
              DASH
            ) : (
              <>
                <span className="text-[--color-feedback-success]">{beats}</span>
                {" / "}
                <span className="text-[--color-feedback-error]">{misses}</span>
              </>
            )
          }
        />
        <Stat
          label="Avg. surprise"
          value={avgSurprise ?? DASH}
          tone={avgSurprise && avgSurprise.startsWith("-") ? "neg" : "pos"}
        />
        <Stat label="Avg. latency" value={avgLatency ?? DASH} />
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "pos" | "neg";
}) {
  const toneClass =
    tone === "pos"
      ? "text-[--color-feedback-success]"
      : tone === "neg"
        ? "text-[--color-feedback-error]"
        : "text-[--color-text-primary]";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9.5px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span
        className={`font-mono text-[22px] tabular-nums leading-none ${toneClass}`}
      >
        {value}
      </span>
    </div>
  );
}
