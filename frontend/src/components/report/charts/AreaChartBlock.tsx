import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface AreaSeries {
  name: string;
  data: { x: string | number; y: number }[];
}

export interface AreaChartBlockProps {
  type: 'area_chart';
  title: string;
  series: AreaSeries[];
  stacked?: boolean;
  options?: { height?: ChartHeight; show_legend?: boolean };
  forcedHeight?: ForcedHeight;
}

export function AreaChartBlock({
  title,
  series,
  stacked = false,
  options,
  forcedHeight,
}: AreaChartBlockProps) {
  const categories = series[0]?.data.map((d) => d.x) ?? [];
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { show: options?.show_legend !== false, bottom: 0 },
    xAxis: { type: 'category', data: categories },
    yAxis: { type: 'value' },
    series: series.map((s) => ({
      type: 'line',
      name: s.name,
      stack: stacked ? 'total' : undefined,
      areaStyle: {},
      smooth: true,
      data: s.data.map((d) => d.y),
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
