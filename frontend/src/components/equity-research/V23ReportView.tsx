/**
 * V23ReportView — render a completed v2.3 run's structured payload.
 *
 * This is the React renderer half of the "one source of truth, two
 * renderers" model spelled out in report_output_rendering_spec.md.
 * The same payload backs the .docx writer on the server; nothing here
 * parses the docx — both renderings come straight from the structured
 * report.
 *
 * Inline markers in section bodies:
 *   `[^N]`           -> superscript footnote anchor linking to #fn-N
 *   `{{FIG:<id>}}`   -> the SVG chart for chart spec <id> with caption
 *
 * Anything else is paragraph text, separated by blank lines.
 */
import { Printer } from "lucide-react";
import { type JSX, type ReactNode, useCallback, useMemo } from "react";

import type {
  V23BundleFact,
  V23ChartSpec,
  V23RunPayload,
} from "../../api/equity-research-v2-3";
import { V23ChartSVG } from "./V23ChartSVG";
import { V23ValuationCard } from "./V23ValuationCard";

interface Props {
  payload: V23RunPayload;
}

const FOOTNOTE_RE = /\[\^(\d+)\]/g;
const FIG_RE = /\{\{FIG:([a-zA-Z0-9_]+)\}\}/g;

export function V23ReportView({ payload }: Props): JSX.Element {
  const chartsById = useMemo<Record<string, V23ChartSpec>>(
    () => Object.fromEntries(payload.charts.map((c) => [c.id, c])),
    [payload.charts],
  );

  const print = useCallback(() => {
    if (typeof window !== "undefined") window.print();
  }, []);

  return (
    <article
      data-testid="er-v2-3-report-view"
      data-print-target="v23-report"
      className="flex flex-col gap-4 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-5 py-5 text-[13.5px] leading-[1.55] text-[--color-text-primary]"
    >
      <PrintBar onPrint={print} />
      <ReportHeader payload={payload} />
      <Thesis payload={payload} />
      <V23ValuationCard payload={payload} />

      {payload.sections.map((section) => {
        const body = payload.section_bodies[section.id] ?? "";
        return (
          <section
            key={section.id}
            id={`section-${section.id}`}
            data-testid={`er-v2-3-section-${section.id}`}
          >
            <h3 className="mb-2 font-display text-[15px] font-semibold tracking-[-0.005em]">
              {section.title}
            </h3>
            <SectionBody
              body={body}
              chartsById={chartsById}
              bundleFacts={payload.bundle_facts}
              figureLabels={payload.figure_labels}
            />
          </section>
        );
      })}

      <Footnotes lines={payload.footnotes} />
    </article>
  );
}

function PrintBar({ onPrint }: { onPrint: () => void }): JSX.Element {
  return (
    <div
      data-print-hide="true"
      className="flex items-center justify-end"
    >
      <button
        type="button"
        onClick={onPrint}
        data-testid="er-v2-3-print"
        className="inline-flex items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
      >
        <Printer size={11} /> Save as PDF
      </button>
    </div>
  );
}


function ReportHeader({ payload }: { payload: V23RunPayload }): JSX.Element {
  return (
    <header className="border-b border-[--color-border-subtle] pb-3">
      <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        {payload.tickers.join(", ")} · {payload.report_type} · {payload.language}
      </div>
      <h2 className="mt-1 font-display text-[19px] font-semibold tracking-[-0.01em]">
        {payload.thesis.central_argument}
      </h2>
    </header>
  );
}

function Thesis({ payload }: { payload: V23RunPayload }): JSX.Element {
  const { key_takeaways, valuation_stance, canonical_figures } = payload.thesis;
  return (
    <section className="rounded-md bg-[--color-bg-elevated] px-4 py-3">
      {key_takeaways.length > 0 ? (
        <>
          <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
            Key takeaways
          </div>
          <ul className="mb-3 list-disc pl-5">
            {key_takeaways.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </>
      ) : null}
      {valuation_stance ? (
        <div className="mb-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
            Valuation
          </span>{" "}
          <span className="text-[--color-text-secondary]">{valuation_stance}</span>
        </div>
      ) : null}
      {canonical_figures.length > 0 ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-[--color-text-secondary]">
          {canonical_figures.map((cf) => (
            <span key={cf.fact_id}>
              <span className="font-mono text-[11px] text-[--color-text-tertiary]">
                {cf.fact_id}
              </span>{" "}
              {cf.display}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

interface SectionBodyProps {
  body: string;
  chartsById: Record<string, V23ChartSpec>;
  bundleFacts: Record<string, V23BundleFact>;
  figureLabels: Record<string, number>;
}

/** Split a section body into paragraphs + figure placeholders, then
 *  inline footnote anchors per paragraph. Blank lines delimit paragraphs;
 *  a {{FIG:id}} token on its own paragraph renders the chart in place. */
function SectionBody({
  body,
  chartsById,
  bundleFacts,
  figureLabels,
}: SectionBodyProps): JSX.Element {
  const paragraphs = splitParagraphs(body);
  return (
    <>
      {paragraphs.map((para, idx) => {
        const figId = paraIsLoneFigure(para);
        if (figId !== null) {
          const spec = chartsById[figId];
          if (spec === undefined) {
            return (
              <p
                key={idx}
                className="my-3 rounded-md border border-dashed border-[--color-feedback-warning] px-3 py-2 font-mono text-[11px] text-[--color-feedback-warning]"
              >
                Missing chart: {figId}
              </p>
            );
          }
          return (
            <V23ChartSVG
              key={idx}
              spec={spec}
              bundleFacts={bundleFacts}
              figureLabel={figureLabels[figId]}
            />
          );
        }
        return (
          <p key={idx} className="my-2">
            {renderInline(para, chartsById, bundleFacts, figureLabels)}
          </p>
        );
      })}
    </>
  );
}

function splitParagraphs(body: string): string[] {
  return body
    .split(/\n{2,}/g)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

function paraIsLoneFigure(para: string): string | null {
  const trimmed = para.trim();
  const match = /^\{\{FIG:([a-zA-Z0-9_]+)\}\}$/.exec(trimmed);
  return match ? match[1] : null;
}

/** Walk a paragraph and translate `[^N]` markers to <sup> anchors and any
 *  inline `{{FIG:id}}` to a small inline-chart slot. */
function renderInline(
  para: string,
  chartsById: Record<string, V23ChartSpec>,
  bundleFacts: Record<string, V23BundleFact>,
  figureLabels: Record<string, number>,
): ReactNode[] {
  // We have two pattern types; tokenize by collecting all matches by index.
  type Token = { kind: "text"; text: string } | { kind: "fn"; n: number } | {
    kind: "fig";
    id: string;
  };
  const tokens: Token[] = [];
  let cursor = 0;
  const combined = new RegExp(
    `${FOOTNOTE_RE.source}|${FIG_RE.source}`,
    "g",
  );
  let m: RegExpExecArray | null;
  while ((m = combined.exec(para)) !== null) {
    if (m.index > cursor) tokens.push({ kind: "text", text: para.slice(cursor, m.index) });
    if (m[1] !== undefined) tokens.push({ kind: "fn", n: Number(m[1]) });
    else if (m[2] !== undefined) tokens.push({ kind: "fig", id: m[2] });
    cursor = m.index + m[0].length;
  }
  if (cursor < para.length) tokens.push({ kind: "text", text: para.slice(cursor) });

  return tokens.map((t, i) => {
    if (t.kind === "text") return <span key={i}>{t.text}</span>;
    if (t.kind === "fn") {
      return (
        <sup key={i} className="ml-[1px] text-[10px] text-[--color-text-secondary]">
          <a href={`#fn-${t.n}`} className="hover:underline">
            [{t.n}]
          </a>
        </sup>
      );
    }
    // Inline figure marker (not on its own paragraph) — render a compact slot.
    const spec = chartsById[t.id];
    if (spec === undefined) {
      return (
        <span key={i} className="font-mono text-[11px] text-[--color-feedback-warning]">
          {`{{FIG:${t.id}}}`}
        </span>
      );
    }
    return (
      <span key={i} className="block">
        <V23ChartSVG spec={spec} bundleFacts={bundleFacts} figureLabel={figureLabels[t.id]} />
      </span>
    );
  });
}

function Footnotes({ lines }: { lines: string[] }): JSX.Element | null {
  if (lines.length === 0) return null;
  return (
    <section
      data-testid="er-v2-3-footnotes"
      className="mt-2 border-t border-[--color-border-subtle] pt-3"
    >
      <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        Footnotes
      </div>
      <ol className="list-decimal pl-5 text-[12px] text-[--color-text-secondary]">
        {lines.map((line, i) => (
          <li key={i} id={`fn-${i + 1}`} className="my-[2px]">
            {line}
          </li>
        ))}
      </ol>
    </section>
  );
}
