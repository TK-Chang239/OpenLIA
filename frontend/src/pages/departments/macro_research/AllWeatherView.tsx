import { useEffect, useRef, useState } from "react";

import { getDashboard, runAssessment } from "../../../api/macro_research";
import type {
  AllWeatherData,
  Status,
  T3CaveatCard,
  T3CoverageCell,
  T3DonutCard,
  T3GoldNeedle,
  T3GoldStat,
  T3RiskBar,
  T3SliceTone,
  T3Tone,
} from "../../../lib/macro_research/dalio_copy/types";
import {
  AllocBar,
  DashEmpty,
  DashHero,
  DashLoading,
  ProseCard,
  SectionLabel,
  Spill,
  SrcFoot,
  Verdict,
} from "../../../components/macro_research/_shared/widgets";
import { Donut } from "../../../components/macro_research/_shared/visuals";

const POLL_INTERVAL_MS = 6000;
const POLL_MAX_ATTEMPTS = 70; // ~7 min; a real macro run takes a few minutes

function toneToStatus(tone: T3Tone): Status {
  switch (tone) {
    case "red":   return "bad";
    case "amber": return "warn";
    case "green": return "ok";
    case "blue":  return "info";
  }
}

function fillForRiskBar(pct: number): Status {
  if (pct > 60) return "bad";
  if (pct > 40) return "warn";
  return "ok";
}

export default function AllWeatherView(): JSX.Element {
  const [data, setData] = useState<AllWeatherData | null>(null);
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
    getDashboard<AllWeatherData>("all_weather")
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
      getDashboard<AllWeatherData>("all_weather")
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
    runAssessment("all_weather")
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

  return (
    <article>
      <DashHero
        eyebrow={data.header.subtitle}
        headline={data.header.title}
        lede={data.gold.rationale.body.split(".")[0] + "."}
      />

      <SectionLabel first>{data.comparison.label}</SectionLabel>
      <div className="mr-grid2" data-testid="t3-comparison" style={{ marginBottom: 14 }}>
        <DonutCard card={data.comparison.benchmark} />
        <DonutCard card={data.comparison.reference} />
      </div>

      <SectionLabel>{data.coverage.label}</SectionLabel>
      <div className="mr-coverage-grid" data-testid="t3-coverage-map" style={{ marginBottom: 14 }}>
        {data.coverage.cells.map((c) => (
          <CoverageCellEl key={c.title} cell={c} />
        ))}
      </div>

      <SectionLabel>{data.riskParity.label}</SectionLabel>
      <div className="mr-card" data-testid="t3-risk-parity" style={{ padding: "16px 18px", marginBottom: 14 }}>
        <p className="mr-card-body-text">{data.riskParity.intro}</p>
        <BarSection
          title={data.riskParity.benchmarkTitle}
          bars={data.riskParity.benchmarkBars}
          testid="t3-risk-bars-benchmark"
        />
        <BarSection
          title={data.riskParity.referenceTitle}
          bars={data.riskParity.referenceBars}
          testid="t3-risk-bars-reference"
        />
        <div className="mr-card-sm" style={{ marginTop: 14, background: "var(--color-bg-base)" }}>
          <div className="mr-card-title">{data.riskParity.mechanism.title}</div>
          <div className="mr-card-body-text">{data.riskParity.mechanism.body}</div>
        </div>
      </div>

      <SectionLabel>{data.gold.label}</SectionLabel>
      <div className="mr-card" data-testid="t3-gold-check" style={{ padding: "18px 22px", marginBottom: 14 }}>
        <div className="mr-card-title" style={{ marginBottom: 10 }}>{data.gold.title}</div>
        <AllocBar
          ticks={["0%", "5%", "7.5%", "10%", "15%", "20%+"]}
          needles={data.gold.needles.map((n: T3GoldNeedle) => ({
            label: n.label,
            pct: n.leftPct,
            tone: toneToStatus(n.tone),
          }))}
        />
        <div className="mr-grid3" style={{ marginTop: 18 }}>
          {data.gold.stats.map((s: T3GoldStat) => (
            <div key={s.label} className="mr-card-sm" style={{ background: "var(--color-bg-base)" }}>
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
              <div
                className="mr-card-title"
                style={{
                  fontSize: 22,
                  fontFamily: "var(--font-mono)",
                  color:
                    s.valueTone === "red"   ? "var(--color-feedback-error)" :
                    s.valueTone === "amber" ? "var(--color-feedback-warning)" :
                    s.valueTone === "green" ? "var(--color-feedback-success)" :
                    "var(--color-text-primary)",
                }}
              >
                {s.value}
              </div>
              <div className="mr-card-body-text">{s.note}</div>
            </div>
          ))}
        </div>
        <div className="mr-card-sm" style={{ marginTop: 14, background: "var(--color-bg-base)" }}>
          <div className="mr-card-title">{data.gold.rationale.title}</div>
          <div className="mr-card-body-text">{data.gold.rationale.body}</div>
        </div>
      </div>

      <SectionLabel>{data.caveats.label}</SectionLabel>
      <div className="mr-grid2" data-testid="t3-caveats" style={{ marginBottom: 14 }}>
        {data.caveats.cards.map((c: T3CaveatCard) => (
          <ProseCard key={c.title} title={c.title} body={c.body} />
        ))}
      </div>

      <Verdict
        testid="t3-verdict"
        meta={
          <>
            T3 SYNTHESIS · DALIO FRAMEWORK <span className="dot" /> April 2026
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

/* ───── T3-only widgets ───── */

function DonutCard({ card }: { card: T3DonutCard }): JSX.Element {
  return (
    <div className="mr-donut">
      <div className="mr-donut-title">{card.title}</div>
      <Donut slices={card.slices} />
      <div className="mr-donut-legend">
        {card.slices.map((s) => (
          <span key={s.label} className="mr-donut-legend-item">
            <span className={`swatch ${sliceClass(s.tone)}`} />
            {s.label} {Number.isInteger(s.pct) ? `${s.pct}%` : `${s.pct.toFixed(1)}%`}
          </span>
        ))}
      </div>
    </div>
  );
}

function sliceClass(tone: T3SliceTone): string {
  return `mr-slice-${tone}`;
}

function CoverageCellEl({ cell }: { cell: T3CoverageCell }): JSX.Element {
  return (
    <div className={`mr-coverage-cell ${toneToStatus(cell.bodyTone)}`}>
      <div className="mr-coverage-head">
        <div className="mr-coverage-title">{cell.title}</div>
        <Spill status={toneToStatus(cell.badgeTone)}>{cell.badgeLabel}</Spill>
      </div>
      <div className="mr-coverage-body">{cell.body}</div>
      <div className="mr-coverage-bridge">
        <strong>{cell.bridgeLabel}:</strong> {cell.bridge}
      </div>
    </div>
  );
}

function BarSection({
  title,
  bars,
  testid,
}: {
  title: string;
  bars: T3RiskBar[];
  testid: string;
}): JSX.Element {
  return (
    <div className="mr-bar-section" data-testid={testid}>
      <div className="mr-bar-section-title">{title}</div>
      {bars.map((b) => {
        const tone = fillForRiskBar(b.pct);
        return (
          <div key={b.label} className="mr-bar-row">
            <div className="mr-bar-label">{b.label}</div>
            <div className="mr-bar-track">
              <div
                className={`mr-bar-fill ${tone === "bad" ? "mr-fill-bad" : tone === "warn" ? "mr-fill-warn" : "mr-fill-ok"}`}
                style={{ width: `${b.pct}%` }}
              />
            </div>
            <div className="mr-bar-val">{Math.round(b.pct)}%</div>
          </div>
        );
      })}
    </div>
  );
}
