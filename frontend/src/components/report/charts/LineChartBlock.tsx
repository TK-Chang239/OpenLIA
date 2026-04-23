import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface LineSeries {
  name: string;
  data: { x: string | number; y: number }[];
}

export interface LineChartBlockProps {
  type: 'line_chart';
  title: string;
  series: LineSeries[];
  x_label?: string;
  y_label?: string;
  options?: { height?: ChartHeight; show_legend?: boolean; show_grid?: boolean };
  forcedHeight?: ForcedHeight;
}

export function LineChartBlock({
  title,
  series,
  x_label,
  y_label,
  options,
  forcedHeight,
}: LineChartBlockProps) {
  const categories = series[0]?.data.map((d) => d.x) ?? [];
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { show: options?.show_legend !== false, bottom: 0 },
    xAxis: { type: 'category', data: categories, name: x_label },
    yAxis: { type: 'value', name: y_label, splitLine: { show: options?.show_grid !== false } },
    series: series.map((s) => ({
      type: 'line',
      name: s.name,
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
