import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { stripCitationMarkers } from "../../../lib/citations";

import "./styles.css";
import type {
  CascadeStep,
  ConsolidatedTrigger,
  DepMapEdge,
  DepMapNode,
  FrameworkStatusCard,
  LiaTake,
  RegimeBarSegment,
  Status,
  SummaryData,
} from "../../../lib/macro_research/dalio_copy/types";
import {
  DepMap as DepMapSVG,
  MiniBars,
  MiniForces,
  MiniQuadrant,
  MiniRing,
  MiniStage,
  SpotlightAreaChart,
} from "./visuals";
import { SectionLabel, SectionSub, Spill } from "./widgets";

/* ============================================================
   Summary-only widgets. Consumed only by SummaryView.
   ============================================================ */

function statusToValClass(s: Status): string {
  return s;
}

/* ===== Hero band (large headline + LIA take side card) ===== */

export function SummaryHero({
  hero,
  liaTake,
}: {
  hero: SummaryData["hero"];
  liaTake: LiaTake;
}): JSX.Element {
  return (
    <section className="mr-summary-hero">
      <div className="left">
        <span className="eyebrow">
          {hero.eyebrow}
          {hero.eyebrowStrong ? <strong>{hero.eyebrowStrong}</strong> : null}
        </span>
        <h1>
          {hero.headline} <span className="accent">{hero.headlineAccent}</span>
        </h1>
        <p className="lede">{hero.lede}</p>
        <div className="stat-row">
          {hero.stats.map((s) => (
            <div key={s.k} className="mr-hstat">
              <span className="k">{s.k}</span>
              <span className={`v ${statusToValClass(s.status)}`}>{s.v}</span>
            </div>
          ))}
        </div>
      </div>
      <LiaTakeCard take={liaTake} />
    </section>
  );
}

function renderInline(text: string): ReactNode {
  // **bold** and *italic* markdown-lite; ledger citation markers are
  // stripped because dashboard payloads carry no citation table.
  const parts = stripCitationMarkers(text).split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={i}>{p.slice(2, -2)}</strong>;
    }
    if (p.startsWith("*") && p.endsWith("*") && p.length > 2) {
      return <em key={i}>{p.slice(1, -1)}</em>;
    }
    return <span key={i}>{p}</span>;
  });
}

function LiaTakeCard({ take }: { take: LiaTake }): JSX.Element {
  return (
    <div className="mr-lia-take" data-testid="summary-lia-take">
      <div className="head">
        <div className="av">LIA</div>
        <div>
          <div className="name">
            LIA's <strong>{take.label.replace(/^LIA's\s*/i, "").replace(/^cross.*/i, "cross-framework take")}</strong>
          </div>
        </div>
        <div className="ts">{take.timestamp}</div>
      </div>
      <div className="body">
        {take.paragraphs.map((p, i) => (
          <p key={i}>{renderInline(p)}</p>
        ))}
      </div>
      <div className="pulls">
        {take.pulls.map((p) => (
          <div key={p.k} className="pull">
            <span className="k">{p.k}</span>
            <span className="v">{p.v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===== Regime bar — at-a-glance verdict band ===== */

export function RegimeBar({
  segments,
  testid,
}: {
  segments: RegimeBarSegment[];
  testid?: string;
}): JSX.Element {
  return (
    <div className="mr-regime-bar" data-testid={testid}>
      {segments.map((s) => (
        <div key={s.k} className="seg">
          <span className="k">{s.k}</span>
          <span className={`v ${statusToValClass(s.status)}`}>{s.v}</span>
          <span className="sub">{s.sub}</span>
        </div>
      ))}
    </div>
  );
}

/* ===== Framework grid (5 cards · T1 spotlight) ===== */

function MiniVisualSwitch({ card }: { card: FrameworkStatusCard }): JSX.Element | null {
  if (card.miniVisual === "bars" && Array.isArray(card.miniData))
    return <MiniBars values={card.miniData} status={card.stamp.status} />;
  if (card.miniVisual === "quadrant" && !Array.isArray(card.miniData))
    return <MiniQuadrant active={card.miniData} />;
  if (card.miniVisual === "ring" && Array.isArray(card.miniData))
    return <MiniRing values={card.miniData} />;
  if (card.miniVisual === "stage" && !Array.isArray(card.miniData))
    return <MiniStage active={card.miniData} />;
  if (card.miniVisual === "forces" && Array.isArray(card.miniData))
    return <MiniForces values={card.miniData} />;
  return null;
}

const MotionLink = motion(Link);

export function FrameworkGrid({
  cards,
  testid,
}: {
  cards: FrameworkStatusCard[];
  testid?: string;
}): JSX.Element {
  const prefersReducedMotion = useReducedMotion();
  const stagger = prefersReducedMotion ? 0 : 0.06;
  return (
    <motion.div
      className="mr-fw-grid"
      data-testid={testid}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: stagger, delayChildren: 0.05 } },
      }}
    >
      {cards.map((c) => (
        <MotionLink
          key={c.tcode}
          to={`/macro-research/${c.slug}`}
          className={`mr-fw-card ${c.spotlight ? "spotlight" : ""}`}
          variants={
            prefersReducedMotion
              ? { hidden: { opacity: 0 }, visible: { opacity: 1 } }
              : {
                  hidden: { opacity: 0, y: 14 },
                  visible: {
                    opacity: 1,
                    y: 0,
                    transition: { duration: 0.32, ease: [0.16, 1, 0.3, 1] },
                  },
                }
          }
          whileHover={prefersReducedMotion ? undefined : { y: -2 }}
          whileTap={prefersReducedMotion ? undefined : { scale: 0.985 }}
          transition={{ type: "spring", stiffness: 380, damping: 26 }}
        >
          <div className="top">
            <div className="badge">
              <span className="code">{c.tcode}</span>
              <span className="name">{c.title}</span>
            </div>
            <Spill status={c.stamp.status}>{c.stamp.label}</Spill>
          </div>
          <p className="verdict-line">
            {c.spotlight && c.verdictLine ? renderInline(c.verdictLine) : c.summary}
          </p>
          {c.spotlight && c.spotlightChart ? (
            <div className="mr-fw-spotlight-vis">
              <SpotlightAreaChart data={c.spotlightChart} />
            </div>
          ) : (
            <div style={{ display: "flex", justifyContent: "center", padding: "4px 0" }}>
              <MiniVisualSwitch card={c} />
            </div>
          )}
          <div className="stats">
            {c.stats.map((s) => (
              <div key={s.k} className="s">
                <span className="k">{s.k}</span>
                <span className={`v ${s.status ?? ""}`}>{s.v}</span>
              </div>
            ))}
          </div>
          <div className="foot">
            <span className="foot-label">{c.footLabel}</span>
            <span className="arrow">→</span>
          </div>
        </MotionLink>
      ))}
    </motion.div>
  );
}

/* ===== Cross-framework dependency map ===== */

export function DepMap({
  nodes,
  edges,
  testid,
}: {
  nodes: DepMapNode[];
  edges: DepMapEdge[];
  testid?: string;
}): JSX.Element {
  return (
    <div className="mr-dep-map" data-testid={testid}>
      <DepMapSVG nodes={nodes} edges={edges} />
      <div className="mr-dep-legend">
        <div className="l">
          <span className="swatch" style={{ background: "var(--color-text-primary)", height: 2 }} />
          Direct numeric feed
        </div>
        <div className="l">
          <span
            className="swatch"
            style={{
              borderTop: "1.4px dashed var(--color-text-secondary)",
              height: 0,
              background: "transparent",
            }}
          />
          Conceptual cross-check
        </div>
        <div className="l">
          <span
            className="swatch"
            style={{ background: "var(--color-feedback-success)", height: 2.5 }}
          />
          Confluence response
        </div>
      </div>
    </div>
  );
}

/* ===== Gold thesis cascade ===== */

function CascadeStepEl({ step }: { step: CascadeStep }): JSX.Element {
  return (
    <div className={`step ${step.target ? "target" : ""}`}>
      <span className="badge">{step.badge}</span>
      <span className="h">{step.title}</span>
      <span className="b">{renderInline(step.body)}</span>
    </div>
  );
}

export function Cascade({
  row1,
  row2,
  testid,
}: {
  row1: CascadeStep[];
  row2: CascadeStep[];
  testid?: string;
}): JSX.Element {
  return (
    <div className="mr-cascade" data-testid={testid}>
      <div className="mr-cascade-row">
        {row1.map((s, i) => (
          <Fragment key={s.title}>
            <CascadeStepEl step={s} />
            {i < row1.length - 1 ? <span className="arr">→</span> : null}
          </Fragment>
        ))}
      </div>
      <div className="mr-cascade-row">
        {row2.map((s, i) => (
          <Fragment key={s.title}>
            <CascadeStepEl step={s} />
            {i < row2.length - 1 ? <span className="arr final">⇒</span> : null}
          </Fragment>
        ))}
        <span className="arr" />
        <div />
      </div>
    </div>
  );
}

/* ===== Consolidated watchlist ===== */

export function ConsolidatedWatchlist({
  triggers,
  testid,
}: {
  triggers: ConsolidatedTrigger[];
  testid?: string;
}): JSX.Element {
  return (
    <div className="mr-watch-grid" data-testid={testid}>
      {triggers.map((t) => (
        <div key={t.name} className="mr-watch">
          <div className="hd">
            <span className={`dot ${t.status}`} />
            <span className="name">{t.name}</span>
            <span className="src">{t.source}</span>
          </div>
          <div className="desc">{t.desc}</div>
          <div className="from">
            <span className="mr-dep-chip">{t.fromTabs}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* Re-export helpers used by SummaryView */
export { SectionLabel, SectionSub };
