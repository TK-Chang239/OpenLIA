// frontend/src/components/report/charts/ComboChartBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface ComboSeries { name: string; values: number[]; }

export interface ComboChartBlockProps {
  type: 'combo_chart';
  title: string;
  categories: string[];
  bar_series: ComboSeries[];
  line_series: ComboSeries[];
  y_left_label?: string;
  y_right_label?: string;
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function ComboChartBlock({
  title,
  categories,
  bar_series,
  line_series,
  y_left_label,
  y_right_label,
  options,
  forcedHeight,
}: ComboChartBlockProps) {
  const option = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 50, right: 50, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: categories },
    yAxis: [
      { type: 'value', name: y_left_label, position: 'left' },
      { type: 'value', name: y_right_label, position: 'right' },
    ],
    series: [
      ...bar_series.map((s) => ({ type: 'bar', name: s.name, data: s.values, yAxisIndex: 0 })),
      ...line_series.map((s) => ({ type: 'line', name: s.name, data: s.values, yAxisIndex: 1, smooth: true })),
    ],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
