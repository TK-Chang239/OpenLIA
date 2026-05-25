/**
 * v2.3 -> v2.2 pill-label bridge.
 *
 * The composer chrome (WelcomeStage + ErComposer) renders a `mode:
 * ReportMode` label sourced from the v2.2 vocabulary
 * (`stock_initiation` / `stock_update` / `sector_research`). The v2.3
 * launch payload uses `report_type: V23ReportType` (`initiation` /
 * `update` / `sector_research`) — a separate value owned by
 * `v23Selection.reportType`. When the user picks a new template in the
 * v2.3 settings modal, the engine's launch payload updates instantly,
 * but the pill is reading from `config.report_mode` (the v2.2 setting)
 * which never changes — so the visible label silently contradicts the
 * actual selection. This mapper bridges the two vocabularies so the
 * pill stays a truthful preview of what the next run will launch with.
 */
import type { ReportMode } from "../../api/equity-research";
import type { V23ReportType } from "../../api/equity-research-v2-3";

export function v23ReportTypeToPillMode(reportType: V23ReportType): ReportMode {
  switch (reportType) {
    case "initiation":
      return "stock_initiation";
    case "update":
      return "stock_update";
    case "sector_research":
      return "sector_research";
  }
}
