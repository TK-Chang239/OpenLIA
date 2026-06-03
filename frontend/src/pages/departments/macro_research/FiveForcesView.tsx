import { type ReactNode, useEffect, useRef, useState } from "react";

import { getDashboard, runAssessment } from "../../../api/macro_research";
import type {
  FiveForcesData,
  Status,
  T5ActiveCount,
  T5ForceRow,
  T5GoldAllocation,
  T5LoopBlock,
  T5SignalCard,
  T5Tone,
} from "../../../lib/macro_research/dalio_copy/types";
import {
  AllocBar,
  DashEmpty,
  DashHero,
  DashLoading,
  ScenarioDuo,
  SectionLabel,
  Spill,
  SrcFoot,
  Verdict,
} from "../../../components/macro_research/_shared/widgets";

const POLL_INTERVAL_MS = 6000;
const POLL_MAX_ATTEMPTS = 70; // ~7 min; a real macro run takes a few minutes

function toneToStatus(tone: T5Tone): Status {
  switch (tone) {
    case "red":   return "bad";
    case "amber": return "warn";
    case "green": return "ok";
    case "blue":  return "info";
  }
}

function fillClassFromStatus(s: Status): string {
  switch (s) {
    case "bad":  return "mr-fill-bad";
    case "warn": return "mr-fill-warn";
    case "ok":
    case "info": return "mr-fill-ok";
    case "acid": return "mr-fill-acid";
    case "flat": return "mr-fill-flat";
  }
}

function renderRich(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={i}>{p.slice(2, -2)}</strong>;
    }
    return <span key={i}>{p}</span>;
  });
}

export default function FiveForcesView(): JSX.Element {
  const [data, setData] = useState<FiveForcesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [, setGeneratedAt] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const load = () => {
    setLoading(true);
    getDashboard<FiveForcesData>("five_forces")
      .then((r) => {
        setData(r.payload);
        setGeneratedAt(r.generated_at);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    return stopPolling;
  }, []);

  const startPolling = () => {
    stopPolling();
    let attempts = 0;
    pollRef.current = setInterval(() => {
      attempts += 1;
      getDashboard<FiveForcesData>("five_forces")
        .then((r) => {
          if (r.payload) {
            stopPolling();
            setData(r.payload);
            setGeneratedAt(r.generated_at);
            setGenerating(false);
            setNote(null);
          } else if (attempts >= POLL_MAX_ATTEMPTS) {
            stopPolling();
            setGenerating(false);
            setNote("Still generating. Reload in a moment to see the result.");
          }
        })
        .catch(() => undefined);
    }, POLL_INTERVAL_MS);
  };

  const onGenerate = () => {
    setNote(
      "Generating a live reading from current data — this can take a few minutes. Keep this tab open.",
    );
    setGenerating(true);
    runAssessment("five_forces")
      .then((r) => {
        if (r.status === "queued") {
          startPolling();
        } else if (r.status === "already_running") {
          // A run is already in flight (e.g. another tab) — watch for it.
          setNote("A reading is already being generated — watching for the result.");
          startPolling();
        } else {
          setGenerating(false);
          setNote("Generation could not start (background scheduler unavailable).");
        }
      })
      .catch(() => {
        setGenerating(false);
        setNote("Could not start generation. Please try again.");
      });
  };

  if (loading) return <DashLoading />;
  if (!data) return <DashEmpty onGenerate={onGenerate} generating={generating} note={note} />;

  const critical = data.scorecard.rows.filter((r) => r.scorePct >= 70).length;
  const aggregate = data.scorecard.rows.length > 0
    ? data.scorecard.rows.reduce((s, r) => s + r.scorePct, 0) / data.scorecard.rows.length / 10
    : 0;

  const heroStats = [
    { k: "Aggregate", v: aggregate.toFixed(1), status: aggregate >= 7 ? "bad" as Status : aggregate >= 5 ? "warn" as Status : "ok" as Status },
    { k: "Critical", v: String(critical), status: critical >= 3 ? "bad" as Status : critical >= 1 ? "warn" as Status : "ok" as Status },
    { k: "Forces", v: `${data.scorecard.rows.length} / 5`, status: "info" as Status },
  ];

  return (
    <article>
      <DashHero
        eyebrow={data.header.subtitle}
        headline={data.header.title}
        lede={data.cardSummary}
        stats={heroStats}
      />

      <SectionLabel first count={data.scorecard.label}>
        Section A — five-force scorecard
      </SectionLabel>
      <div className="mr-card" data-testid="t5-scorecard" style={{ padding: "4px 18px", marginBottom: 14 }}>
        {data.scorecard.rows.map((r) => (
          <ForceRowEl key={r.forceLabel} row={r} />
        ))}
      </div>

      <SectionLabel count={data.loops.label}>
        Section B — reinforcement loops
      </SectionLabel>
      <div className="mr-grid2" data-testid="t5-loops" style={{ marginBottom: 14 }}>
        {data.loops.blocks.map((b: T5LoopBlock) => (
          <div key={b.title} className="mr-loop">
            <div className="lt">{b.title}</div>
            {b.arrows.map((a, i) => (
              <div key={i} className="arr">
                <span className="chip">{a.fromLabel}</span>
                <span className="sym">→</span>
                <span className="chip">{a.toLabel}</span>
              </div>
            ))}
            <p>{b.body}</p>
          </div>
        ))}
      </div>
      <ActiveCount active={data.loops.active} />

      <SectionLabel count={data.signals.label}>Section C — market signals</SectionLabel>
      <div className="mr-grid3" data-testid="t5-signals" style={{ marginBottom: 14 }}>
        {data.signals.cards.map((c: T5SignalCard) => (
          <div key={c.label} className="mr-card-sm" style={{ background: "var(--color-bg-elevated)" }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "var(--color-text-tertiary)",
              }}
            >
              {c.label}
            </div>
            <div className="mr-card-title" style={{ fontSize: 22, fontFamily: "var(--font-mono)" }}>{c.value}</div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--color-text-tertiary)",
              }}
            >
              {c.unit}
            </div>
            <div className="mr-card-body-text">{c.note}</div>
          </div>
        ))}
      </div>

      <SectionLabel count={data.goldAllocation.label}>
        Section D — gold allocation framework
      </SectionLabel>
      <GoldAllocationCard block={data.goldAllocation.block} />

      <SectionLabel count={data.scenarios.label}>Section E — scenarios</SectionLabel>
      <div data-testid="t5-scenarios" style={{ marginBottom: 14 }}>
        {data.scenarios.cards.length >= 2 ? (
          <ScenarioDuo
            bull={(() => {
              const c = data.scenarios.cards.find((x) => x.variant === "bull");
              return { label: "Bull case", title: c?.title ?? "—", body: c?.body ?? "" };
            })()}
            bear={(() => {
              const c = data.scenarios.cards.find((x) => x.variant === "bear");
              return { label: "Bear case", title: c?.title ?? "—", body: c?.body ?? "" };
            })()}
          />
        ) : null}
      </div>

      <Verdict
        testid="t5-verdict"
        meta={
          <>
            T5 SYNTHESIS · DALIO FRAMEWORK <span className="dot" /> April 2026
          </>
        }
        headline={data.verdict.title}
        body={data.verdict.body}
      />

      <SrcFoot>
        <strong>Sources · </strong>
        {data.sources}
      </SrcFoot>
    </article>
  );
}

/* ───── T5-only widgets ───── */

function ForceRowEl({ row }: { row: T5ForceRow }): JSX.Element {
  return (
    <div className="mr-force-row">
      <div className="mr-force-meta">
        <span className="fnum">{row.forceLabel}</span>
        <span className="fname">{row.forceSub}</span>
        <Spill status={toneToStatus(row.pillTone)}>{row.pillLabel}</Spill>
        <div className="fbar" style={{ marginTop: 6 }}>
          <div
            className={`ff ${fillClassFromStatus(toneToStatus(row.scoreTone))}`}
            style={{ width: `${row.scorePct}%` }}
          />
        </div>
        <div className="fscore">
          <span className="num">{row.scoreValue}</span>
        </div>
      </div>
      <div className="mr-force-body">{renderRich(row.body)}</div>
      <div className="mr-force-status" />
    </div>
  );
}

function ActiveCount({ active }: { active: T5ActiveCount }): JSX.Element {
  return (
    <div className={`mr-active ${toneToStatus(active.countTone)}`} data-testid="t5-active-count" style={{ marginBottom: 14 }}>
      <div className="mr-active-num">{active.countText}</div>
      <div>
        <div className="mr-active-title">{active.title}</div>
        <div className="mr-active-body">{active.body}</div>
      </div>
    </div>
  );
}

function GoldAllocationCard({ block }: { block: T5GoldAllocation }): JSX.Element {
  return (
    <div className="mr-card" data-testid="t5-gold-allocation" style={{ padding: "18px 22px", marginBottom: 14 }}>
      <div className="mr-card-title" style={{ marginBottom: 14 }}>{block.title}</div>
      <AllocBar
        ticks={block.ticks}
        needles={block.stats
          .filter((s) => s.highlight)
          .map((s) => ({ label: s.label, pct: 50, tone: "warn" as Status }))}
      />
      <div className="mr-grid3" style={{ marginTop: 18 }}>
        {block.stats.map((s) => (
          <div
            key={s.label}
            className="mr-card-sm"
            style={{
              background: s.highlight ? "rgba(var(--color-accent-primary-rgb), 0.10)" : "var(--color-bg-base)",
              borderColor: s.highlight ? "var(--color-accent-primary)" : undefined,
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "var(--color-text-tertiary)",
              }}
            >
              {s.label}
            </div>
            <div className="mr-card-title" style={{ fontSize: 18, fontFamily: "var(--font-mono)" }}>{s.value}</div>
            <div className="mr-card-body-text">{s.note}</div>
          </div>
        ))}
      </div>
      <p className="mr-card-body-text" style={{ marginTop: 14 }}>{block.body}</p>
    </div>
  );
}
