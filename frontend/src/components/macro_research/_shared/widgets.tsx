import type { ReactNode } from "react";

import "./styles.css";
import type { Status } from "../../../lib/macro_research/dalio_copy/types";

/* ============================================================
   Shared widget vocabulary used across all 6 macro tabs.
   Generic, tone-driven components consume the existing data
   shapes via small adapters in each tab view.
   ============================================================ */

function fillClassFor(status: Status): string {
  switch (status) {
    case "bad":  return "mr-fill-bad";
    case "warn": return "mr-fill-warn";
    case "ok":
    case "info": return "mr-fill-ok";
    case "acid": return "mr-fill-acid";
    case "flat": return "mr-fill-flat";
  }
}

function valToneClass(status: Status): string {
  return status; // matches the .v.bad/.warn/.ok/.info/.acid/.flat selectors
}

/* ===== Section label (horizontal-rule header) ===== */

export function SectionLabel({
  children,
  count,
  aiTag,
  first,
}: {
  children: ReactNode;
  count?: string;
  aiTag?: string;
  first?: boolean;
}): JSX.Element {
  return (
    <div className={`mr-sec ${first ? "first" : ""}`}>
      <span>{children}</span>
      <span className="ln" />
      {count ? <span className="count">{count}</span> : null}
      {aiTag ? <span className="ai-tag">{aiTag}</span> : null}
    </div>
  );
}

export function SectionSub({ children }: { children: ReactNode }): JSX.Element {
  return <p className="mr-sec-sub">{children}</p>;
}

/* ===== Spill / pill ===== */

export function Spill({
  status,
  children,
}: {
  status: Status;
  children: ReactNode;
}): JSX.Element {
  return (
    <span className={`mr-spill ${status}`}>
      <span className="d" />
      {children}
    </span>
  );
}

/* ===== Hero band ===== */

export interface HeroStat {
  k: string;
  v: string;
  status: Status;
  unit?: string;
}

export function DashHero({
  eyebrow,
  eyebrowGrey,
  headline,
  headlineAccent,
  lede,
  stats,
  side,
}: {
  eyebrow: string;
  eyebrowGrey?: string;
  headline: string;
  headlineAccent?: string;
  lede: ReactNode;
  stats?: HeroStat[];
  side?: ReactNode;
}): JSX.Element {
  return (
    <section className="mr-hero">
      <div className="left">
        <span className="eyebrow">
          {eyebrow}
          {eyebrowGrey ? <span className="grey">{eyebrowGrey}</span> : null}
        </span>
        <h1>
          {headline}
          {headlineAccent ? <span className="accent"> {headlineAccent}</span> : null}
        </h1>
        <p className="lede">{lede}</p>
        {stats && stats.length > 0 ? (
          <div className="stat-row">
            {stats.map((s) => (
              <div key={s.k} className="mr-hstat">
                <span className="k">{s.k}</span>
                <span className={`v ${valToneClass(s.status)}`}>
                  {s.v}
                  {s.unit ? <small>{s.unit}</small> : null}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      {side ? <div className="mr-hero-side">{side}</div> : <div />}
    </section>
  );
}

/* ===== Score table ===== */

export interface ScoreRow {
  name: string;
  sub: string;
  fillPct: number;
  fillStatus: Status;
  current: string;
  currentStatus: Status;
  currentMeta: string;
  ctx?: ReactNode;
  /** Optional 4th column: extra metric, e.g. trend or context line. */
  extra?: ReactNode;
  status: { label: string; tone: Status };
}

export function ScoreTable({
  rows,
  headers,
  testid,
}: {
  rows: ScoreRow[];
  /** Column headers — controls grid columns: 4 or 5 (with extra). */
  headers: string[];
  testid?: string;
}): JSX.Element {
  const cols = headers.length;
  return (
    <div className={`mr-score cols-${cols}`} data-testid={testid}>
      <div className="head">
        {headers.map((h, i) => (
          <span key={i}>{h}</span>
        ))}
      </div>
      {rows.map((r) => (
        <div key={r.name} className="row">
          <div>
            <div className="name">{r.name}</div>
            <div className="sub">{r.sub}</div>
            <div className="track">
              <div
                className={`fill ${fillClassFor(r.fillStatus)}`}
                style={{ width: `${r.fillPct}%` }}
              />
            </div>
          </div>
          <div>
            <div className={`val ${valToneClass(r.currentStatus)}`}>
              {r.current}
              <small>{r.currentMeta}</small>
            </div>
          </div>
          {cols >= 4 ? <div className="ctx">{r.ctx}</div> : null}
          {cols >= 5 ? <div className="ctx">{r.extra}</div> : null}
          <div className="status">
            <Spill status={r.status.tone}>{r.status.label}</Spill>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ===== Indicator card (compact ind block) ===== */

export function IndCard({
  name,
  value,
  unit,
  status,
  body,
  fillPct,
}: {
  name: string;
  value: string;
  unit?: string;
  status: Status;
  body?: ReactNode;
  fillPct?: number;
}): JSX.Element {
  return (
    <div className="mr-ind">
      <div className="row1">
        <div className="name">{name}</div>
        <Spill status={status}>{status.toUpperCase()}</Spill>
      </div>
      <div className="row2">
        <div className={`val ${valToneClass(status)}`}>{value}</div>
        {unit ? <div className="unit">{unit}</div> : null}
      </div>
      {fillPct !== undefined ? (
        <div className="gauge">
          <div className={`fill ${fillClassFor(status)}`} style={{ width: `${fillPct}%` }} />
        </div>
      ) : null}
      {body ? <div className="body">{body}</div> : null}
    </div>
  );
}

/* ===== Verdict callout ===== */

export function Verdict({
  meta,
  headline,
  body,
  tone,
  badge = "LIA",
  tags,
  testid,
}: {
  meta?: ReactNode;
  headline: string;
  body: ReactNode;
  tone?: Status;
  badge?: string;
  tags?: { label: string; href?: string }[];
  testid?: string;
}): JSX.Element {
  return (
    <div className={`mr-verdict ${tone ?? ""}`} data-testid={testid}>
      <div className="badge">{badge}</div>
      <div className="body">
        {meta ? <div className="meta">{meta}</div> : null}
        <h2>{headline}</h2>
        <p>{body}</p>
        {tags && tags.length > 0 ? (
          <div className="tags">
            {tags.map((t) =>
              t.href ? (
                <a key={t.label} href={t.href} className="tag">
                  {t.label}
                </a>
              ) : (
                <span key={t.label} className="tag">
                  {t.label}
                </span>
              ),
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* ===== Phase strip ===== */

export interface PhaseCell {
  name: string;
  pill?: string;
  state: "past" | "active" | "future";
  /** weight for past cells (1..4 darker) */
  weight?: number;
  /** active-only colour override; default red */
  tone?: Status;
}

export function PhaseStrip({
  cells,
  testid,
}: {
  cells: PhaseCell[];
  testid?: string;
}): JSX.Element {
  return (
    <div className="mr-phase-strip" data-testid={testid}>
      {cells.map((c, i) => (
        <div
          key={`${c.name}-${i}`}
          className={`mr-pstage ${c.state}${c.weight ? ` is-w-${c.weight}` : ""} ${c.state === "active" && c.tone ? c.tone : ""}`}
        >
          <div className="pname">{c.name}</div>
          {c.pill ? <div className="ppill">{c.pill}</div> : null}
        </div>
      ))}
    </div>
  );
}

/* ===== Loading skeleton ===== */

export function DashLoading({ testid }: { testid?: string }): JSX.Element {
  return (
    <article className="mr-dash-loading" data-testid={testid ?? "mr-dash-loading"}>
      <div className="mr-skel mr-skel-hero" />
      <div className="mr-skel mr-skel-line" />
      <div className="mr-skel mr-skel-block" />
      <div className="mr-skel mr-skel-line" />
      <div className="mr-skel mr-skel-block" />
    </article>
  );
}

/* ===== Empty state ===== */

export function DashEmpty({
  onGenerate,
  generating,
  testid,
}: {
  onGenerate: () => void;
  generating?: boolean;
  testid?: string;
}): JSX.Element {
  return (
    <article className="mr-dash-empty" data-testid={testid ?? "mr-dash-empty"}>
      <div className="mr-card-sm mr-dash-empty-card">
        <div className="mr-card-title">This dashboard hasn&rsquo;t been generated yet.</div>
        <div className="mr-card-body-text">
          Run the assessment to produce a live reading from current data.
        </div>
        <button
          type="button"
          className="mr-dash-empty-btn"
          onClick={onGenerate}
          disabled={generating}
          data-testid="mr-dash-empty-generate"
        >
          {generating ? "Generating…" : "Generate now"}
        </button>
      </div>
    </article>
  );
}

/* ===== Source footer ===== */

export function SrcFoot({ children }: { children: ReactNode }): JSX.Element {
  return <p className="mr-src-foot">{children}</p>;
}

/* ===== Bull / bear scenario duo ===== */

export function ScenarioDuo({
  bull,
  bear,
}: {
  bull: { label: string; title: string; body: string };
  bear: { label: string; title: string; body: string };
}): JSX.Element {
  return (
    <div className="mr-scen-duo">
      <div className="mr-scen bull">
        <span className="st">{bull.label}</span>
        <h4>{bull.title}</h4>
        <p>{bull.body}</p>
      </div>
      <div className="mr-scen bear">
        <span className="st">{bear.label}</span>
        <h4>{bear.title}</h4>
        <p>{bear.body}</p>
      </div>
    </div>
  );
}

/* ===== Card pair (eyebrow + title + body) ===== */

export function ProseCard({
  eyebrow,
  title,
  body,
}: {
  eyebrow?: string;
  title: string;
  body: string;
}): JSX.Element {
  return (
    <div className="mr-card-sm">
      {eyebrow ? <SectionLabel>{eyebrow}</SectionLabel> : null}
      <div className="mr-card-title">{title}</div>
      <div className="mr-card-body-text">{body}</div>
    </div>
  );
}

/* ===== Allocation bar ===== */

export interface AllocNeedle {
  label: string;
  pct: number;
  tone?: Status;
}

export function AllocBar({
  ticks,
  needles,
  testid,
}: {
  ticks: string[];
  needles: AllocNeedle[];
  testid?: string;
}): JSX.Element {
  return (
    <div className="mr-alloc" data-testid={testid}>
      <div className="mr-alloc-track">
        <div className="mr-alloc-fill" />
        {needles.map((n) => (
          <div key={n.label} className="mr-alloc-needle" style={{ left: `${n.pct}%` }}>
            <span className="lbl">{n.label}</span>
          </div>
        ))}
      </div>
      <div className="mr-alloc-axis">
        {ticks.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
    </div>
  );
}
