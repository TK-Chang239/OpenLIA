import type { JSX } from "react";
import type { PanelChrome } from "../../../lib/panic_thermometer/copy/types";

interface Props {
  panel: PanelChrome;
}

export function PanelHead({ panel }: Props): JSX.Element {
  return (
    <div className="pt-panel-head">
      <div className="pt-num">{panel.num}</div>
      <div className="pt-nm">
        {panel.title}
        <small>{panel.subtitle}</small>
      </div>
      <div className="pt-spacer" />
      <span className={`pt-pill is-${panel.pillTone}`}>{panel.pillLabel}</span>
      <span className="pt-lupd">{panel.lastUpdate}</span>
    </div>
  );
}
