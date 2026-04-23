// frontend/src/components/report/charts/ScatterBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface ScatterSeries { name: string; data: { x: number; y: number }[]; }

export interface ScatterBlockProps {
  type: 'scatter_plot';
  title: string;
  series: ScatterSeries[];
  x_label?: string;
  y_label?: string;
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function ScatterBlock({ title, series, x_label, y_label, options, forcedHeight }: ScatterBlockProps) {
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value', name: x_label },
    yAxis: { type: 'value', name: y_label },
    series: series.map((s) => ({
      type: 'scatter',
      name: s.name,
      data: s.data.map((d) => [d.x, d.y]),
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
