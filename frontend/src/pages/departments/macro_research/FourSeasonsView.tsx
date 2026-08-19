import { useEffect, useRef, useState } from "react";

import { getDashboard, runAssessment } from "../../../api/macro_research";
import { CitationTableContext } from "../../../lib/citationLinks";
import type {
  FourSeasonsData,
  Status,
  T2AssetCard,
  T2Direction,
  T2QuadrantMarker,
  T2QuadrantSeason,
  T2ScorecardRow,
  T2Tone,
  T2TransitionProb,
} from "../../../lib/macro_research/dalio_copy/types";
import {
  DashEmpty,
  DashHero,
  DashLoading,
  ProseCard,
  ScenarioDuo,
  SectionLabel,
  Spill,
  SrcFoot,
  Verdict,
} from "../../../components/macro_research/_shared/widgets";

function fmtProb(p: number): string {
  return `${(p * 100).toFixed(0)}%`;
}

const POLL_INTERVAL_MS = 6000;
const POLL_MAX_ATTEMPTS = 70; // ~7 min; a real macro run takes a few minutes

function toneToStatus(tone: T2Tone): Status {
  switch (tone) {
    case "red":    return "bad";
    case "amber":  return "warn";
    case "green":  return "ok";
    case "blue":   return "info";
    case "purple": return "acid";
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

export default function FourSeasonsView(): JSX.Element {
  const [data, setData] = useState<FourSeasonsData | null>(null);
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
    getDashboard<FourSeasonsData>("four_seasons")
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
      getDashboard<FourSeasonsData>("four_seasons")
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
    runAssessment("four_seasons")
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

  const heroStats = data.scorecard.rows
    .slice(0, 4)
    .map((r) => ({
      k: r.name.replace(/\s*\(.*\)/, "").split(",")[0].trim(),
      v: r.current,
      status: toneToStatus(r.currentTone),
    }));

  return (
    <CitationTableContext.Provider value={data.citations ?? null}>
    <article>
      <DashHero
        eyebrow={data.header.subtitle}
        headline={data.header.title}
        lede={data.transitionRisk.intro}
        stats={heroStats}
      />

      <SectionLabel first count={`${data.scorecard.rows.length} indicators`}>
        Section A — quadrant inputs
      </SectionLabel>
      <T2Scorecard rows={data.scorecard.rows} />

      <SectionLabel>Section B — current macro regime</SectionLabel>
      <QuadrantMap seasons={data.quadrant.seasons} markers={data.quadrant.markers} />

      <div className="mr-card" data-testid="t2-verdict" style={{ padding: "18px 20px", margin: "16px 0" }}>
        <SectionLabel>Primary season verdict</SectionLabel>
        <div className="mr-card-title" style={{ fontSize: 18, marginTop: 8 }}>
          {data.verdict.title}
        </div>
        <div className="mr-card-body-text" style={{ marginTop: 6 }}>
          {data.verdict.body}
        </div>
        <div className="mr-grid3" style={{ marginTop: 14 }}>
          {data.verdict.sideCards.map((s) => (
            <div key={s.label} className="mr-card-sm">
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
                  fontSize: 18,
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
      </div>

      <SectionLabel>Section C — historical parallels & transition risk</SectionLabel>
      <div className="mr-grid2" style={{ marginBottom: 14 }}>
        {data.parallels.cards.map((c) => (
          <ProseCard key={c.title} title={c.title} body={c.body} />
        ))}
      </div>
      <div className="mr-card" data-testid="t2-transition-risk" style={{ padding: "18px 20px", marginBottom: 14 }}>
        <p className="mr-card-body-text" style={{ marginBottom: 14 }}>
          {data.transitionRisk.intro}
        </p>
        <ScenarioDuo
          bull={{ label: "Bull case", title: data.transitionRisk.bull.title, body: data.transitionRisk.bull.body }}
          bear={{ label: "Bear case", title: data.transitionRisk.bear.title, body: data.transitionRisk.bear.body }}
        />
        <div
          className="mr-card-sm"
          data-testid="t2-transition-probabilities"
          style={{ marginTop: 14 }}
        >
          <div className="mr-card-title">
            Regime transition probabilities (from {data.transitionRisk.probabilities.currentSeason})
          </div>
          <div className="mr-bar-section" style={{ marginTop: 8 }}>
            <div className="mr-bar-section-title">Next quarter</div>
            {data.transitionRisk.probabilities.nextQuarter.map((p: T2TransitionProb) => (
              <div key={p.season} className="mr-bar-row">
                <div className="mr-bar-label">{p.season}</div>
                <div className="mr-bar-track">
                  <div
                    className={`mr-bar-fill ${
                      p.season === data.transitionRisk.probabilities.adverseSeason ? "mr-fill-bad" : "mr-fill-ok"
                    }`}
                    style={{ width: `${p.prob * 100}%` }}
                  />
                </div>
                <div className="mr-bar-val">{fmtProb(p.prob)}</div>
              </div>
            ))}
          </div>
          <div className="mr-grid3" style={{ marginTop: 12 }}>
            <div>
              <div className="mr-card-title">Persistence</div>
              <div className="mr-card-body-text">
                {fmtProb(data.transitionRisk.probabilities.persistence)} stay in{" "}
                {data.transitionRisk.probabilities.currentSeason} · ~
                {data.transitionRisk.probabilities.expectedDwellQuarters.toFixed(1)}q dwell
              </div>
            </div>
            <div>
              <div className="mr-card-title">Most likely next</div>
              <div className="mr-card-body-text">
                {data.transitionRisk.probabilities.mostLikelyNext}
              </div>
            </div>
            <div>
              <div className="mr-card-title">
                P(&rarr; {data.transitionRisk.probabilities.adverseSeason})
              </div>
              <div className="mr-card-body-text">
                {fmtProb(data.transitionRisk.probabilities.adverseProb)} next quarter
              </div>
            </div>
          </div>
          <div className="mr-bar-section">
            <div className="mr-bar-section-title">
              {data.transitionRisk.probabilities.horizonQuarters} quarters ahead
            </div>
            {data.transitionRisk.probabilities.horizon.map((p: T2TransitionProb) => (
              <div key={p.season} className="mr-bar-row">
                <div className="mr-bar-label">{p.season}</div>
                <div className="mr-bar-track">
                  <div
                    className={`mr-bar-fill ${
                      p.season === data.transitionRisk.probabilities.adverseSeason ? "mr-fill-bad" : "mr-fill-ok"
                    }`}
                    style={{ width: `${p.prob * 100}%` }}
                  />
                </div>
                <div className="mr-bar-val">{fmtProb(p.prob)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="mr-card-sm" style={{ marginTop: 14 }}>
          <div className="mr-card-title">{data.transitionRisk.keyIndicator.title}</div>
          <div className="mr-card-body-text">{data.transitionRisk.keyIndicator.body}</div>
        </div>
      </div>

      <SectionLabel>Section D — asset playbook</SectionLabel>
      <div className="mr-grid4" data-testid="t2-asset-playbook" style={{ marginBottom: 14 }}>
        {data.assetPlaybook.cards.map((c) => (
          <AssetTile key={c.label} card={c} />
        ))}
      </div>

      {data.notes.length > 0 ? (
        <div className="mr-grid2" style={{ marginBottom: 14 }}>
          {data.notes.map((n) => (
            <ProseCard key={n.title} title={n.title} body={n.body} />
          ))}
        </div>
      ) : null}

      <Verdict
        meta={
          <>
            T2 SYNTHESIS · DALIO FRAMEWORK <span className="dot" /> April 2026
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
    </CitationTableContext.Provider>
  );
}

/* ───── T2-only widgets ───── */

function T2Scorecard({ rows }: { rows: T2ScorecardRow[] }): JSX.Element {
  const cols = "minmax(0,1.6fr) minmax(0,0.9fr) minmax(0,1.0fr) 100px 110px";
  return (
    <div className="mr-score" data-testid="t2-scorecard">
      <div className="head" style={{ gridTemplateColumns: cols }}>
        <span>Indicator</span>
        <span>Current</span>
        <span>3-month trend</span>
        <span>Axis signal</span>
        <span>Direction</span>
      </div>
      {rows.map((r) => (
        <T2Row key={r.name} row={r} cols={cols} />
      ))}
    </div>
  );
}

function T2Row({ row, cols }: { row: T2ScorecardRow; cols: string }): JSX.Element {
  const fillStatus = toneToStatus(row.fillTone);
  return (
    <div className="row" style={{ gridTemplateColumns: cols }}>
      <div>
        <div className="name">{row.name}</div>
        <div className="sub">{row.sub}</div>
        <div className="track">
          <div className={`fill ${fillClassFromStatus(fillStatus)}`} style={{ width: `${row.fillPct}%` }} />
        </div>
      </div>
      <div>
        <div className={`val ${toneToStatus(row.currentTone)}`}>
          {row.current}
          <small>{row.currentMeta}</small>
        </div>
      </div>
      <div className="ctx">{row.trend}</div>
      <div>
        <Spill status={toneToStatus(row.axisTone)}>{row.axisLabel}</Spill>
      </div>
      <div className={`ctx ${toneToStatus(row.directionTone)}`} style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <DirectionGlyph direction={row.direction} />
        <span>{row.directionLabel}</span>
      </div>
    </div>
  );
}

function DirectionGlyph({ direction }: { direction: T2Direction }): JSX.Element {
  const ch = direction === "up" ? "▲" : direction === "down" ? "▼" : "▬";
  return <span aria-hidden>{ch}</span>;
}

function QuadrantMap({
  seasons,
  markers,
}: {
  seasons: FourSeasonsData["quadrant"]["seasons"];
  markers: T2QuadrantMarker[];
}): JSX.Element {
  return (
    <div className="mr-quadrant" data-testid="t2-quadrant-map">
      <div className="mr-quadrant-axis-h" />
      <div className="mr-quadrant-axis-v" />
      <div className="mr-quadrant-axis-label t-top">Inflation rising</div>
      <div className="mr-quadrant-axis-label t-bottom">Inflation falling</div>
      <div className="mr-quadrant-axis-label t-left">Growth falling</div>
      <div className="mr-quadrant-axis-label t-right">Growth rising</div>

      <QuadrantCell season={seasons.tl} />
      <QuadrantCell season={seasons.tr} />
      <QuadrantCell season={seasons.bl} />
      <QuadrantCell season={seasons.br} />

      {markers.map((m) => (
        <Marker key={m.label} marker={m} />
      ))}
    </div>
  );
}

function QuadrantCell({ season }: { season: T2QuadrantSeason }): JSX.Element {
  return (
    <div className={`mr-quadrant-cell ${toneToStatus(season.tone)}`}>
      <div className="name">{season.name}</div>
      <div className="sub">{season.sub}</div>
      <div className="pill">{season.pillLabel}</div>
    </div>
  );
}

function Marker({ marker }: { marker: T2QuadrantMarker }): JSX.Element {
  const labelTop = `${Math.min(marker.yPct + 8, 96)}%`;
  return (
    <>
      <div
        className={`mr-quadrant-marker ${marker.variant === "prev" ? "is-prev" : ""}`}
        style={{ left: `${marker.xPct}%`, top: `${marker.yPct}%` }}
        data-testid={`t2-quadrant-marker-${marker.variant}`}
      >
        <div className="core" />
      </div>
      <div className="mr-quadrant-marker-label" style={{ left: `${marker.xPct}%`, top: labelTop }}>
        {marker.label}
      </div>
    </>
  );
}

function AssetTile({ card }: { card: T2AssetCard }): JSX.Element {
  return (
    <div className={`mr-asset-tile ${toneToStatus(card.tone)}`}>
      <span className="lbl">{card.label}</span>
      <span className="posture">{card.posture}</span>
      <span className="body">{card.body}</span>
    </div>
  );
}
