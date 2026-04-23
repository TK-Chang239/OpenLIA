import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface BarSeries {
  name: string;
  values: number[];
}

export interface BarChartBlockProps {
  type: 'bar_chart';
  title: string;
  categories: string[];
  series: BarSeries[];
  orientation?: 'vertical' | 'horizontal';
  stacked?: boolean;
  options?: { height?: ChartHeight; show_legend?: boolean; show_grid?: boolean };
  forcedHeight?: ForcedHeight;
}

export function BarChartBlock({
  title,
  categories,
  series,
  orientation = 'vertical',
  stacked = false,
  options,
  forcedHeight,
}: BarChartBlockProps) {
  const horizontal = orientation === 'horizontal';
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { show: options?.show_legend !== false, bottom: 0 },
    xAxis: horizontal
      ? { type: 'value', splitLine: { show: options?.show_grid !== false } }
      : { type: 'category', data: categories },
    yAxis: horizontal
      ? { type: 'category', data: categories }
      : { type: 'value', splitLine: { show: options?.show_grid !== false } },
    series: series.map((s) => ({
      type: 'bar',
      name: s.name,
      stack: stacked ? 'total' : undefined,
      data: s.values,
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
