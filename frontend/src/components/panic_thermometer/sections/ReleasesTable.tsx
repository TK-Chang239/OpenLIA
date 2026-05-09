import type { JSX } from "react";
import type { ReleaseRow } from "../../../lib/panic_thermometer/copy/types";

interface Props {
  rows: ReleaseRow[];
}

export function ReleasesTable({ rows }: Props): JSX.Element {
  return (
    <>
      <div className="pt-sec-label">
        <span>Macro releases · last 7 days</span>
        <span className="pt-ln" />
        <span className="pt-count">economic_events · US</span>
      </div>

      <section
        className="pt-mtable"
        role="table"
        aria-label="Macro releases last 7 days"
      >
        <div className="pt-mt-row is-head" role="row">
          <span role="columnheader">When</span>
          <span role="columnheader">Release</span>
          <span style={{ textAlign: "right" }} role="columnheader">
            Actual
          </span>
          <span style={{ textAlign: "right" }} className="pt-col-hide" role="columnheader">
            Consensus
          </span>
          <span style={{ textAlign: "right" }} className="pt-col-hide" role="columnheader">
            Prior
          </span>
          <span style={{ textAlign: "right" }} role="columnheader">
            Surprise
          </span>
        </div>

        {rows.map((r, i) => (
          <div key={i} className="pt-mt-row" role="row">
            <span className="pt-when" role="cell">
              <strong>{r.whenDay}</strong>
              {r.whenTime}
            </span>
            <span className="pt-nm" role="cell">
              {r.name}
              <small>{r.source}</small>
            </span>
            <span className={`pt-num is-${r.actualTone}`} role="cell">
              {r.actual}
            </span>
            <span className="pt-num pt-col-hide" role="cell">
              {r.consensus}
            </span>
            <span className="pt-num pt-col-hide" role="cell">
              {r.prior}
            </span>
            <span className={`pt-num is-${r.surpriseTone}`} role="cell">
              {r.surprise}
              {r.surpriseTag ? <small>{r.surpriseTag}</small> : null}
            </span>
          </div>
        ))}
      </section>
    </>
  );
}
