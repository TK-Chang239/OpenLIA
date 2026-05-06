import { TextBlock } from './blocks/TextBlock';
import { TableBlock } from './blocks/TableBlock';
import { MetricCardsBlock } from './blocks/MetricCardsBlock';
import { KeyFindingBlock } from './blocks/KeyFindingBlock';
import { RatingBadgeBlock } from './blocks/RatingBadgeBlock';
import { GroupBlock, type ForcedHeight } from './blocks/GroupBlock';
import { PullQuoteBlock } from './blocks/PullQuoteBlock';
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

export interface BlockRendererProps {
  block: any;
  forcedHeight?: ForcedHeight;
}

export function BlockRenderer({ block, forcedHeight }: BlockRendererProps) {
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
    case 'group':
      return (
        <GroupBlock
          {...block}
          renderChild={(child: any, forced) => (
            <BlockRenderer block={child} forcedHeight={forced} />
          )}
        />
      );
    case 'line_chart':
      return <LineChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'bar_chart':
      return <BarChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'area_chart':
      return <AreaChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'pie_chart':
      return <PieChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'candlestick_chart':
      return <CandlestickBlock {...block} forcedHeight={forcedHeight} />;
    case 'waterfall_chart':
      return <WaterfallBlock {...block} forcedHeight={forcedHeight} />;
    case 'scatter_plot':
      return <ScatterBlock {...block} forcedHeight={forcedHeight} />;
    case 'heatmap':
      return <HeatmapBlock {...block} forcedHeight={forcedHeight} />;
    case 'treemap':
      return <TreemapBlock {...block} forcedHeight={forcedHeight} />;
    case 'combo_chart':
      return <ComboChartBlock {...block} forcedHeight={forcedHeight} />;
    default:
      return (
        <div className="report-block--unsupported" role="alert">
          Unsupported block type: {String(block.type)}
        </div>
      );
  }
}
