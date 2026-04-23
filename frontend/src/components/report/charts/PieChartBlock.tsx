import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface PieSegment {
  label: string;
  value: number;
}

export interface PieChartBlockProps {
  type: 'pie_chart';
  title: string;
  segments: PieSegment[];
  donut?: boolean;
  options?: { height?: ChartHeight; show_legend?: boolean };
  forcedHeight?: ForcedHeight;
}

export function PieChartBlock({
  title,
  segments,
  donut = false,
  options,
  forcedHeight,
}: PieChartBlockProps) {
  const option = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'item' },
    legend: { show: options?.show_legend !== false, bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: donut ? ['45%', '70%'] : [0, '70%'],
        data: segments.map((s) => ({ name: s.label, value: s.value })),
      },
    ],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
