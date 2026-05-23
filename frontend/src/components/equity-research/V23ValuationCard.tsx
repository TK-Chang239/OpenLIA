/**
 * V23ValuationCard — methodology breakdown for a v2.3 run's compute output.
 *
 * Scans the payload's bundle_facts for the deterministic ids that the
 * v2.3 COMPUTE stage emits (see schemas.dcf_result_to_facts,
 * valuation.comps_result_to_facts, valuation.sensitivity_result_to_fact)
 * and surfaces them in a single "Valuation & Price Target" card so the
 * reader doesn't have to dig through the prose to find the numbers.
 *
 * Fact id conventions:
 *   dcf_fair_value              -> per-share fair value (USD)
 *   dcf_enterprise_value        -> total enterprise value (USD millions)
 *   comps_implied_<multiple>    -> one row per implied multiple
 *   sensitivity_grid            -> 2D grid stored as a series payload
 *
 * The card renders nothing when none of these ids are present, so
 * runs without a populated valuation_plan (e.g. morning briefs)
 * simply skip it.
 */
import { type JSX, useMemo } from "react";

import type {
  V23BundleFact,
  V23RunPayload,
} from "../../api/equity-research-v2-3";

interface Props {
  payload: V23RunPayload;
}

interface ValuationRow {
  key: string;
  method: string;
  label: string;
  display: string;
  factId: string;
}

export function V23ValuationCard({ payload }: Props): JSX.Element | null {
  const rows = useMemo(() => extractRows(payload.bundle_facts), [payload.bundle_facts]);
  if (rows.length === 0) return null;
  return (
    <section
      data-testid="er-v2-3-valuation-card"
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 py-3"
    >
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="font-display text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
          Valuation & Price Target
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
          {payload.tickers.join(", ")}
        </div>
      </div>
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="border-b border-[--color-border-subtle] text-left font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            <th className="py-1.5 pr-3 font-medium">Method</th>
            <th className="py-1.5 pr-3 font-medium">Measure</th>
            <th className="py-1.5 pr-3 text-right font-medium">Value</th>
            <th className="py-1.5 text-right font-medium">Fact</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-b border-[--color-border-subtle] last:border-b-0"
              data-testid={`er-v2-3-valuation-row-${row.factId}`}
            >
              <td className="py-2 pr-3 text-[--color-text-secondary]">{row.method}</td>
              <td className="py-2 pr-3 text-[--color-text-primary]">{row.label}</td>
              <td className="py-2 pr-3 text-right font-mono text-[12.5px] text-[--color-text-primary]">
                {row.display}
              </td>
              <td className="py-2 text-right font-mono text-[10px] text-[--color-text-tertiary]">
                <a
                  href={`#fact-${row.factId}`}
                  className="hover:text-[--color-text-secondary] hover:underline"
                >
                  {row.factId}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function extractRows(facts: Record<string, V23BundleFact>): ValuationRow[] {
  const rows: ValuationRow[] = [];

  const dcfFv = facts["dcf_fair_value"];
  if (dcfFv) {
    rows.push({
      key: "dcf-fair-value",
      method: "DCF",
      label: "Fair value per share",
      display: formatValue(dcfFv),
      factId: dcfFv.id,
    });
  }
  const dcfEv = facts["dcf_enterprise_value"];
  if (dcfEv) {
    rows.push({
      key: "dcf-enterprise-value",
      method: "DCF",
      label: "Enterprise value",
      display: formatValue(dcfEv),
      factId: dcfEv.id,
    });
  }

  for (const [id, fact] of Object.entries(facts)) {
    if (!id.startsWith("comps_implied_")) continue;
    const multiple = id.slice("comps_implied_".length);
    rows.push({
      key: `comps-${multiple}`,
      method: "Comps",
      label: `Implied price (${humaniseMultiple(multiple)})`,
      display: formatValue(fact),
      factId: fact.id,
    });
  }

  const sens = facts["sensitivity_grid"];
  if (sens) {
    rows.push({
      key: "sensitivity",
      method: "Sensitivity",
      label: "DCF driver grid",
      display: describeSensitivity(sens),
      factId: sens.id,
    });
  }

  return rows;
}

function humaniseMultiple(raw: string): string {
  // pe -> P/E ; evebitda -> EV/EBITDA ; ps -> P/S
  const known: Record<string, string> = {
    pe: "P/E",
    pb: "P/B",
    ps: "P/S",
    evebitda: "EV/EBITDA",
    evsales: "EV/Sales",
    pfcf: "P/FCF",
  };
  return known[raw] ?? raw.toUpperCase();
}

function formatValue(fact: V23BundleFact): string {
  const v = fact.value;
  if (typeof v === "string") return v;
  if (typeof v === "number") {
    const unit = fact.unit ?? "";
    const formatted = Number.isFinite(v)
      ? v.toLocaleString(undefined, {
          minimumFractionDigits: v < 10 ? 2 : 0,
          maximumFractionDigits: 2,
        })
      : String(v);
    if (unit === "USD") return `$${formatted}`;
    if (unit === "USD_millions") return `$${formatted}M`;
    return unit ? `${formatted} ${unit}` : formatted;
  }
  return `${v.length}-point series`;
}

function describeSensitivity(fact: V23BundleFact): string {
  if (Array.isArray(fact.value)) {
    return `${fact.value.length} grid points`;
  }
  return formatValue(fact);
}
