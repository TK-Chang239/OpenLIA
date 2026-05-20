import type { JSX } from "react";
import { useTranslation } from "react-i18next";

import type { ReleaseRow } from "../../../lib/panic_thermometer/copy/types";

interface Props {
  rows: ReleaseRow[];
}

export function ReleasesTable({ rows }: Props): JSX.Element {
  const { t } = useTranslation();
  return (
    <>
      <div className="pt-sec-label">
        <span>{t("panic_thermometer.releases.title")}</span>
        <span className="pt-ln" />
        <span className="pt-count">{t("panic_thermometer.releases.meta")}</span>
      </div>

      <section
        className="pt-mtable"
        role="table"
        aria-label={t("panic_thermometer.releases.aria")}
      >
        <div className="pt-mt-row is-head" role="row">
          <span role="columnheader">{t("panic_thermometer.releases.col_when")}</span>
          <span role="columnheader">{t("panic_thermometer.releases.col_release")}</span>
          <span style={{ textAlign: "right" }} role="columnheader">
            {t("panic_thermometer.releases.col_actual")}
          </span>
          <span style={{ textAlign: "right" }} className="pt-col-hide" role="columnheader">
            {t("panic_thermometer.releases.col_consensus")}
          </span>
          <span style={{ textAlign: "right" }} className="pt-col-hide" role="columnheader">
            {t("panic_thermometer.releases.col_prior")}
          </span>
          <span style={{ textAlign: "right" }} role="columnheader">
            {t("panic_thermometer.releases.col_surprise")}
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
