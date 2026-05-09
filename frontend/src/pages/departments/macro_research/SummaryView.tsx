import { SUMMARY_FALLBACK } from "../../../lib/macro_research/dalio_copy/summary";
import type { SummaryData } from "../../../lib/macro_research/dalio_copy/types";
import {
  Cascade,
  ConsolidatedWatchlist,
  DepMap,
  FrameworkGrid,
  RegimeBar,
  SummaryHero,
} from "../../../components/macro_research/_shared/summary-widgets";
import { SectionLabel, SectionSub, SrcFoot } from "../../../components/macro_research/_shared/widgets";

export default function SummaryView(): JSX.Element {
  // TODO(backend): const live = useSummary(); const data = live ?? SUMMARY_FALLBACK
  const data: SummaryData = SUMMARY_FALLBACK;

  return (
    <article>
      <SummaryHero hero={data.hero} liaTake={data.liaTake} />

      <SectionLabel first count={data.regimeBar.subLabel}>
        {data.regimeBar.label}
      </SectionLabel>
      <RegimeBar segments={data.regimeBar.segments} testid="summary-regime-bar" />

      <SectionLabel count={data.frameworkStatus.subLabel}>
        {data.frameworkStatus.label}
      </SectionLabel>
      <FrameworkGrid cards={data.frameworkStatus.cards} testid="summary-framework-grid" />

      <SectionLabel count={data.depMap.subLabel}>{data.depMap.label}</SectionLabel>
      <SectionSub>{data.depMap.sub}</SectionSub>
      <DepMap nodes={data.depMap.nodes} edges={data.depMap.edges} testid="summary-dep-map" />

      <SectionLabel count={data.cascade.subLabel}>{data.cascade.label}</SectionLabel>
      <SectionSub>{data.cascade.sub}</SectionSub>
      <Cascade row1={data.cascade.row1} row2={data.cascade.row2} testid="summary-cascade" />

      <SectionLabel count={data.watchlist.subLabel}>{data.watchlist.label}</SectionLabel>
      <ConsolidatedWatchlist triggers={data.watchlist.triggers} testid="summary-watchlist" />

      <SrcFoot>
        <strong>Sources · </strong>
        {data.sources}
      </SrcFoot>
    </article>
  );
}
