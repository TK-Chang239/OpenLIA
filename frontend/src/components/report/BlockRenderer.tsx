import { TextBlock } from './blocks/TextBlock';
import { TableBlock } from './blocks/TableBlock';
import { MetricCardsBlock } from './blocks/MetricCardsBlock';
import { KeyFindingBlock } from './blocks/KeyFindingBlock';
import { RatingBadgeBlock } from './blocks/RatingBadgeBlock';
import { GroupBlock, type ForcedHeight } from './blocks/GroupBlock';
import { PullQuoteBlock } from './blocks/PullQuoteBlock';
import { CalloutGridBlock } from './blocks/CalloutGridBlock';
import { TimelineBlock } from './blocks/TimelineBlock';
import { BulletListBlock } from './blocks/BulletListBlock';
import { ComparisonSplitBlock } from './blocks/ComparisonSplitBlock';
import { QuoteBlock } from './blocks/QuoteBlock';
import { LineChartBlock } from './charts/LineChartBlock';
import { BarChartBlock } from './charts/BarChartBlock';
import { AreaChartBlock } from './charts/AreaChartBlock';
import { PieChartBlock } from './charts/PieChartBlock';
import { CandlestickBlock } from './charts/CandlestickBlock';
import { WaterfallBlock } from './charts/WaterfallBlock';
import { ScatterBlock } from './charts/ScatterBlock';
import { HeatmapBlock } from './charts/HeatmapBlock';
import { TreemapBlock } from './charts/TreemapBlock';
import { ComboChartBlock } from './charts/ComboChartBlock';
import { SkipBannerBlock } from './blocks/SkipBannerBlock';
import { DegradedBannerBlock } from './blocks/DegradedBannerBlock';
import { ChartImageBlock } from './blocks/ChartImageBlock';
import { ExcelAttachmentBlock } from './blocks/ExcelAttachmentBlock';

export interface BlockRendererProps {
  block: any;
  forcedHeight?: ForcedHeight;
  /** When set on a chart block, wraps the chart in
   *  `<div data-block-path="..." data-block-type="...">` so headless export
   *  can locate it and screenshot the rendered chart for DOCX. */
  blockPath?: string;
}

const CHART_TYPES = new Set([
  'line_chart',
  'bar_chart',
  'area_chart',
  'pie_chart',
  'candlestick_chart',
  'waterfall_chart',
  'scatter_plot',
  'heatmap',
  'treemap',
  'combo_chart',
]);

function renderInner(block: any, renderChild?: (child: any, forced: ForcedHeight | undefined) => JSX.Element) {
  switch (block.type) {
    case 'text':
      return <TextBlock content={block.content} />;
    case 'table':
      return <TableBlock {...block} />;
    case 'metric_cards':
      return <MetricCardsBlock {...block} />;
    case 'key_finding':
      return <KeyFindingBlock {...block} />;
    case 'rating_badge':
      return <RatingBadgeBlock {...block} />;
    case 'pull_quote':
      return <PullQuoteBlock {...block} />;
    case 'callout_grid':
      return <CalloutGridBlock {...block} />;
    case 'timeline':
      return <TimelineBlock {...block} />;
    case 'bullet_list':
      return <BulletListBlock {...block} />;
    case 'comparison_split':
      return <ComparisonSplitBlock {...block} />;
    case 'quote':
      return <QuoteBlock {...block} />;
    case 'group':
      return (
        <GroupBlock
          {...block}
          renderChild={
            renderChild ??
            ((child: any, forced) => <BlockRenderer block={child} forcedHeight={forced} />)
          }
        />
      );
    case 'line_chart':
      return <LineChartBlock {...block} />;
    case 'bar_chart':
      return <BarChartBlock {...block} />;
    case 'area_chart':
      return <AreaChartBlock {...block} />;
    case 'pie_chart':
      return <PieChartBlock {...block} />;
    case 'candlestick_chart':
      return <CandlestickBlock {...block} />;
    case 'waterfall_chart':
      return <WaterfallBlock {...block} />;
    case 'scatter_plot':
      return <ScatterBlock {...block} />;
    case 'heatmap':
      return <HeatmapBlock {...block} />;
    case 'treemap':
      return <TreemapBlock {...block} />;
    case 'combo_chart':
      return <ComboChartBlock {...block} />;
    // v2.2 block types — emitted by RunnerV2 helpers and rendered straight
    // through for repo-saved legacy reports.
    case 'skip_banner':
      return <SkipBannerBlock {...block} />;
    case 'degraded_banner':
      return <DegradedBannerBlock {...block} />;
    case 'chart_image':
      return <ChartImageBlock {...block} />;
    case 'excel_attachment':
      return <ExcelAttachmentBlock {...block} />;
    default:
      return (
        <div className="report-block--unsupported" role="alert">
          Unsupported block type: {String(block.type)}
        </div>
      );
  }
}

export function BlockRenderer({ block, forcedHeight: _forcedHeight, blockPath }: BlockRendererProps) {
  const inner = renderInner(block);
  if (blockPath && CHART_TYPES.has(block.type)) {
    return (
      <div data-block-path={blockPath} data-block-type={block.type}>
        {inner}
      </div>
    );
  }
  return inner;
}
