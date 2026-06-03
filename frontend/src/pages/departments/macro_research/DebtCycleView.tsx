import { useEffect, useState } from "react";

import { getDashboard, runAssessment } from "../../../api/macro_research";
import type {
  DebtCycleData,
  Status,
  T1Tone,
} from "../../../lib/macro_research/dalio_copy/types";
import {
  DashEmpty,
  DashHero,
  DashLoading,
  IndCard,
  ProseCard,
  ScoreTable,
  SectionLabel,
  Spill,
  SrcFoot,
  Verdict,
} from "../../../components/macro_research/_shared/widgets";

function toneToStatus(tone: T1Tone): Status {
  switch (tone) {
    case "red": return "bad";
    case "amber": return "warn";
    case "green": return "ok";
    case "blue": return "info";
  }
}

export default function DebtCycleView(): JSX.Element {
  const [data, setData] = useState<DebtCycleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const load = () => {
    setLoading(true);
    getDashboard<DebtCycleData>("debt_cycle")
      .then((r) => {
        setData(r.payload);
        setGeneratedAt(r.generated_at);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const onGenerate = () => {
    setGenerating(true);
    runAssessment("debt_cycle")
      .catch(() => undefined)
      .finally(() => {
        setGenerating(false);
        load();
      });
  };

  if (loading) return <DashLoading />;
  if (!data) return <DashEmpty onGenerate={onGenerate} generating={generating} />;

  const generatedLabel = generatedAt
    ? new Date(generatedAt).toLocaleDateString()
    : "—";

  const heroStats = data.scorecard.rows.map((r) => ({
    k: r.name.replace(/\s*\(.*\)/, "").split("/")[0].trim(),
    v: r.current,
    status: toneToStatus(r.currentTone),
  }));

  return (
    <article>
      <DashHero
        eyebrow={data.header.subtitle}
        headline={data.header.title}
        lede={data.phaseBox.body}
        stats={heroStats}
      />

      <SectionLabel first count={`${data.scorecard.rows.length} indicators`}>
        Section A — headline scorecard
      </SectionLabel>
      <ScoreTable
        testid="t1-scorecard"
        headers={["Indicator", "Current", "Dalio warn threshold", "Status"]}
        rows={data.scorecard.rows.map((r) => ({
          name: r.name,
          sub: r.sub,
          fillPct: r.fillPct,
          fillStatus: toneToStatus(r.fillTone),
          current: r.current,
          currentStatus: toneToStatus(r.currentTone),
          currentMeta: r.currentMeta,
          ctx: r.threshold,
          status: { label: r.status, tone: toneToStatus(r.statusTone) },
        }))}
      />

      <SectionLabel>Section B — cycle phase assessment</SectionLabel>
      <div
        className="mr-card-sm"
        data-testid="t1-phase-box"
        style={{
          padding: "16px 18px",
          borderRadius: 12,
          marginBottom: 14,
          background:
            data.phaseBox.tone === "red"
              ? "color-mix(in srgb, var(--color-feedback-error) 6%, var(--color-bg-elevated))"
              : data.phaseBox.tone === "amber"
                ? "color-mix(in srgb, var(--color-feedback-warning) 8%, var(--color-bg-elevated))"
                : "var(--color-bg-elevated)",
        }}
      >
        <div className="mr-card-title">{data.phaseBox.title}</div>
        <div className="mr-card-body-text">{data.phaseBox.body}</div>
      </div>
      <div className="mr-grid2" style={{ marginBottom: 14 }}>
        <ProseCard
          eyebrow="Historical analog"
          title={data.analogPair.analog.title}
          body={data.analogPair.analog.body}
        />
        <ProseCard
          eyebrow="Time-to-constraint estimate"
          title={data.analogPair.timeToConstraint.title}
          body={data.analogPair.timeToConstraint.body}
        />
      </div>

      <SectionLabel>Section C — monetary policy space</SectionLabel>
      <div className="mr-grid3" style={{ marginBottom: 14 }}>
        {data.policySpace.cards.map((c) => (
          <IndCard
            key={c.label}
            name={c.label}
            value={c.value}
            unit={c.unit}
            status={toneToStatus(c.valueTone)}
            body={c.note}
          />
        ))}
      </div>

      <SectionLabel>Section D — asset implications</SectionLabel>
      <div className="mr-grid2" style={{ marginBottom: 14 }}>
        <ProseCard
          eyebrow="Gold / real assets thesis"
          title={data.assetThesis.gold.title}
          body={data.assetThesis.gold.body}
        />
        <ProseCard
          eyebrow="Long-duration bond risk"
          title={data.assetThesis.longBond.title}
          body={data.assetThesis.longBond.body}
        />
      </div>

      <SectionLabel count={`${data.watchlist.rows.length} triggers`}>
        Watchlist — what would change this assessment
      </SectionLabel>
      <div className="mr-card" data-testid="t1-watchlist" style={{ padding: "4px 18px", marginBottom: 18 }}>
        <div className="mr-trig-list">
          {data.watchlist.rows.map((r) => (
            <div key={r.name} className="mr-trig">
              <span className={`dot ${toneToStatus(r.tone)}`} />
              <div className="name">{r.name}</div>
              <div className="body">{r.body}</div>
              <Spill status={toneToStatus(r.tone)}>{toneToStatus(r.tone)}</Spill>
            </div>
          ))}
        </div>
      </div>

      <Verdict
        testid="t1-verdict"
        meta={<>T1 SYNTHESIS · DALIO FRAMEWORK <span className="dot" /> {generatedLabel}</>}
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
