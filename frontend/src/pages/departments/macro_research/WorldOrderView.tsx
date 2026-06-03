import { useEffect, useRef, useState } from "react";

import { getDashboard, runAssessment } from "../../../api/macro_research";
import type {
  Status,
  T4AnalogCell,
  T4CurrencyRow,
  T4DalioQuote,
  T4GoldRangeStat,
  T4MarkerRow,
  T4ProseCard,
  T4ReserveChart,
  T4ScorecardRow,
  T4StageCell,
  T4Tone,
  WorldOrderData,
} from "../../../lib/macro_research/dalio_copy/types";
import {
  DashEmpty,
  DashHero,
  DashLoading,
  PhaseStrip,
  ProseCard,
  ScoreTable,
  SectionLabel,
  Spill,
  SrcFoot,
  Verdict,
} from "../../../components/macro_research/_shared/widgets";
import { ReserveLineChart } from "../../../components/macro_research/_shared/visuals";

const POLL_INTERVAL_MS = 6000;
const POLL_MAX_ATTEMPTS = 70; // ~7 min; a real macro run takes a few minutes

function toneToStatus(tone: T4Tone): Status {
  switch (tone) {
    case "red":   return "bad";
    case "amber": return "warn";
    case "green": return "ok";
    case "blue":  return "info";
  }
}

export default function WorldOrderView(): JSX.Element {
  const [data, setData] = useState<WorldOrderData | null>(null);
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
    getDashboard<WorldOrderData>("world_order")
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
      getDashboard<WorldOrderData>("world_order")
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
    runAssessment("world_order")
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

  const HERO_KEYS: Record<string, string> = {
    "USD share of global FX reserves": "USD reserve",
    "Net central bank gold purchases": "CB gold",
    "Foreign Treasury holdings trend": "UST held",
    "Dollar Index (DXY)": "DXY",
  };
  const heroStats = data.scorecard.rows.slice(0, 4).map((r: T4ScorecardRow) => ({
    k: HERO_KEYS[r.name] ?? r.name.split(/\s*[/(]/)[0].trim(),
    v: r.current,
    status: toneToStatus(r.currentTone),
  }));

  return (
    <article>
      <DashHero
        eyebrow={data.header.subtitle}
        headline={data.header.title}
        lede={data.empireCycle.quote.body}
        stats={heroStats}
      />

      <SectionLabel first count={`${data.scorecard.rows.length} indicators`}>
        {data.scorecard.label}
      </SectionLabel>
      <ScoreTable
        testid="t4-scorecard"
        headers={["Indicator", "Current", "Trend / context", "Signal"]}
        rows={data.scorecard.rows.map((r) => ({
          name: r.name,
          sub: r.sub,
          fillPct: r.fillPct,
          fillStatus: toneToStatus(r.fillTone),
          current: r.current,
          currentStatus: toneToStatus(r.currentTone),
          currentMeta: r.currentMeta,
          ctx: r.trend,
          status: { label: r.signalLabel, tone: toneToStatus(r.signalTone) },
        }))}
      />

      <ReserveChartCard chart={data.reserveChart} />

      <SectionLabel count={data.empireCycle.label}>
        Section B — empire cycle position
      </SectionLabel>
      <div className="mr-card" data-testid="t4-empire-cycle" style={{ padding: "16px 18px", marginBottom: 14 }}>
        <div className="mr-card-title" style={{ marginBottom: 12 }}>{data.empireCycle.stripTitle}</div>
        <div data-testid="t4-stage-strip">
          <PhaseStrip
            cells={data.empireCycle.stages.map((s: T4StageCell) => ({
              name: `${s.num} · ${s.name}`,
              pill: s.range,
              state: s.state,
              weight: s.weight,
              tone: s.state === "active" ? "warn" : undefined,
            }))}
          />
        </div>

        <DalioQuote quote={data.empireCycle.quote} />

        <div style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--color-text-tertiary)",
          margin: "12px 0 6px",
        }}>
          {data.empireCycle.markersTitle}
        </div>
        <div data-testid="t4-stage-markers">
          {data.empireCycle.markers.map((m) => (
            <MarkerRowEl key={m.leadPhrase} row={m} />
          ))}
        </div>
      </div>

      <SectionLabel count={data.analogs.label}>Section C — historical analog</SectionLabel>
      <div className="mr-analog-grid" data-testid="t4-analog-grid" style={{ marginBottom: 14 }}>
        {data.analogs.cells.map((c: T4AnalogCell) => (
          <div key={c.era} className={`mr-analog-cell ${toneToStatus(c.tone)}`}>
            <div className="mr-analog-head">{c.era}</div>
            <div className="mr-analog-body">{c.body}</div>
          </div>
        ))}
      </div>

      <SectionLabel count={data.wealthShift.label}>
        Section C — wealth shift assessment
      </SectionLabel>
      <div className="mr-card" data-testid="t4-wealth-shift" style={{ padding: "16px 18px", marginBottom: 14 }}>
        <p className="mr-card-body-text" style={{ marginBottom: 12 }}>{data.wealthShift.intro}</p>
        <div data-testid="t4-wealth-shift-rows">
          {data.wealthShift.rows.map((r) => (
            <MarkerRowEl key={r.leadPhrase} row={r} />
          ))}
        </div>
        <div className="mr-card-sm" style={{ marginTop: 12, background: "var(--color-bg-base)" }}>
          <div className="mr-card-title">{data.wealthShift.assessment.title}</div>
          <div className="mr-card-body-text">{data.wealthShift.assessment.body}</div>
        </div>
      </div>

      <SectionLabel count={data.investment.label}>
        Section D — investment implications
      </SectionLabel>
      <div className="mr-grid2" style={{ marginBottom: 10 }}>
        <GoldRangeBlock
          title={data.investment.goldRange.title}
          stats={data.investment.goldRange.stats}
          body={data.investment.goldRange.body}
        />
        <CurrencyExposureBlock
          title={data.investment.currency.title}
          rows={data.investment.currency.rows}
        />
      </div>
      <SovereignBondPremium
        title={data.investment.sovereignBond.title}
        intro={data.investment.sovereignBond.intro}
        pair={data.investment.sovereignBond.pair}
      />

      <Verdict
        testid="t4-verdict"
        meta={
          <>
            T4 SYNTHESIS · DALIO FRAMEWORK <span className="dot" /> April 2026
          </>
        }
        headline={data.verdict.title}
        body={data.verdict.body}
        tone={toneToStatus(data.verdict.tone)}
      />

      <SrcFoot>
        <strong>Sources · </strong>
        {data.sources}
      </SrcFoot>
    </article>
  );
}

/* ───── T4-only widgets ───── */

function ReserveChartCard({ chart }: { chart: T4ReserveChart }): JSX.Element {
  return (
    <div className="mr-card" data-testid="t4-reserve-chart" style={{ padding: "16px 18px", margin: "16px 0 14px" }}>
      <div className="mr-card-title" style={{ marginBottom: 10 }}>{chart.title}</div>
      <ReserveLineChart years={chart.years} series={chart.series} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 10 }}>
        {chart.series.map((s) => (
          <span
            key={s.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--color-text-secondary)",
            }}
          >
            <span
              style={{
                width: 14,
                height: 3,
                borderRadius: 1,
                background:
                  s.label === "USD" ? "var(--color-feedback-error)" :
                  s.label === "EUR" ? "var(--color-text-secondary)" :
                  s.label === "JPY" ? "var(--color-feedback-warning)" :
                  s.label === "CNY" ? "var(--color-feedback-success)" :
                  "var(--color-text-tertiary)",
              }}
            />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function DalioQuote({ quote }: { quote: T4DalioQuote }): JSX.Element {
  const tone = toneToStatus(quote.tone);
  return (
    <div className={`mr-quote ${tone}`} data-testid="t4-dalio-quote" style={{ marginTop: 14 }}>
      <div className="mr-quote-title">{quote.title}</div>
      <div className="mr-quote-body">{quote.body}</div>
      <div className="mr-quote-attribution">{quote.attribution}</div>
    </div>
  );
}

function MarkerRowEl({ row }: { row: T4MarkerRow }): JSX.Element {
  return (
    <div className={`mr-marker-row ${toneToStatus(row.tone)}`}>
      <span className="dot" />
      <span className="pill">{row.pillLabel}</span>
      <div className="body">
        <span className="lead">{row.leadPhrase}</span>
        {row.leadPhrase.endsWith(".") ? " " : " — "}
        {row.body}
      </div>
    </div>
  );
}

function GoldRangeBlock({
  title,
  stats,
  body,
}: {
  title: string;
  stats: T4GoldRangeStat[];
  body: string;
}): JSX.Element {
  return (
    <div className="mr-card" data-testid="t4-gold-range" style={{ padding: "16px 18px" }}>
      <SectionLabel>{title}</SectionLabel>
      <div className="mr-grid3" style={{ marginTop: 8, marginBottom: 10 }}>
        {stats.map((s) => (
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
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--color-text-tertiary)",
              }}
            >
              {s.label}
            </div>
            <div className="mr-card-title" style={{ fontSize: 18, fontFamily: "var(--font-mono)" }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div className="mr-card-body-text">{body}</div>
    </div>
  );
}

function CurrencyExposureBlock({
  title,
  rows,
}: {
  title: string;
  rows: T4CurrencyRow[];
}): JSX.Element {
  return (
    <div className="mr-card" data-testid="t4-currency-exposure" style={{ padding: "16px 18px" }}>
      <SectionLabel>{title}</SectionLabel>
      <div className="mr-curr-table" style={{ marginTop: 8 }}>
        {rows.map((r) => (
          <div key={r.name} className="mr-curr-row">
            <div className="c-name">
              <span className="n">{r.name}</span>
            </div>
            <div className="c-body">{r.body}</div>
            <Spill status={toneToStatus(r.badgeTone)}>{r.badgeLabel}</Spill>
          </div>
        ))}
      </div>
    </div>
  );
}

function SovereignBondPremium({
  title,
  intro,
  pair,
}: {
  title: string;
  intro: string;
  pair: { left: T4ProseCard; right: T4ProseCard };
}): JSX.Element {
  return (
    <div className="mr-card" data-testid="t4-sovereign-bond" style={{ padding: "16px 18px", marginBottom: 14 }}>
      <SectionLabel>{title}</SectionLabel>
      <p className="mr-card-body-text" style={{ marginTop: 8, marginBottom: 12 }}>{intro}</p>
      <div className="mr-grid2">
        <ProseCard title={pair.left.title} body={pair.left.body} />
        <ProseCard title={pair.right.title} body={pair.right.body} />
      </div>
    </div>
  );
}
